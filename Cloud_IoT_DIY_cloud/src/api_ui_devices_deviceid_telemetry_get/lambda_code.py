'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
import json
import logging
import os
import asyncio
import re
from typing import Union, List, Dict

# this is import from layer!
# NOTE that we don't include layer to Lambda deployment package
# instead it's deployed separately and made available for Lambdas (see cloud_iot_diy_cloud/cloud_iot_diy_cloud_stack.py)
if os.environ.get("AWS_LAMBDA_FUNCTION_VERSION", None) is None:
    # this part is required for local debugging only!
    import sys
    sys.path.append("./src")

from _api_handlers_common import aws_common_headers, decode_data_value_by_name
from _objects_datasource import ObjectsDatasource, ObjectsDatasourceFactory, ObjectsDatasourceType
from _devices_registry import DevicesRegistry, DevicesRegistryFactory, DevicesRegistryType

# logging level can/will be redefined in any specific Cloud (Lambda/Azure function/etc.)
# predefined here for local
_root_logger = logging.getLogger()
_root_logger.setLevel(level=logging.INFO)
# instantiate _top_logger to be used in this code
_top_logger = logging.getLogger(__name__)

# define some global variables to benefit from Lambda "hot start"
telemetry_data_sources:Dict[str, ObjectsDatasource] = {}
aws_registry:DevicesRegistry = None

def telemetry_ds_for_deviceid(telemetry_bucket_name:str, device_id:str,
                              telemetry_key:str,
                              telemetry_topic:str,
                              user_groups:str=None,
                              things_group_name:str=None,
                              telemetry_ingest_rule_prefix:str=None)->ObjectsDatasource:
    ''' collect from cache or generate a new DataSource '''
    global telemetry_data_sources, aws_registry

    if device_id in telemetry_data_sources:
        return telemetry_data_sources[device_id]

    #---------------------------------------------------------------------------
    # we need to find the right prefix for this device_id datasource
    # we know that the key can have a rule in the name (if basic ingest is used)
    # AND we know that topic parts are used as a object key in the bucket
    # examples:
    # telemetry_key = ${topic(1)}/${topic(2)}/${topic(6)}/${topic(7)}/${parse_time('yyyy',timestamp())}/${parse_time('MM',timestamp())}/${parse_time('dd',timestamp())}/${timestamp()}
    # telemetry_topic = $aws/rules/TelemetryInjectiondiyiot/dt/diyiot/{{ building_id }}/{{ location_id }}/diy/{{ thing_type }}/{{ thing_name }}
    key_prefix_parts = telemetry_key.split("/")
    if telemetry_topic.startswith("$aws/rules/"):
        # basic ingest is used so we need to remove rule prefix
        telemetry_topic_parts = telemetry_topic.split("/")[3:]
    # key_prefix_parts has a references to topic so we need to do some parsing
    key_prefix = ""
    for key_comp in key_prefix_parts:
        if len(key_prefix)>0:
            key_prefix += "/"
        m=re.match(r"\$\{topic\((?P<topic_index>\d+)\)}", key_comp.replace(" ",""))
        try:
            if not m is None:
                key_prefix += telemetry_topic_parts[int(m.group("topic_index"))-1]
                continue
        except Exception as e:
            _top_logger.warning(f"telemetry_ds_for_deviceid: FAIL to convert {key_comp} to topic part value with exception {e}")
        key_prefix += key_comp
    # now we need to replace thing attributes in the key
    # including {{ building_id }}/{{ location_id }}/{{ things_group_name }}/{{ thing_type }}/{{ thing_name }}
    # we'll not use jinja (overkill for so simple pattern)
    # but we need to find thing attributes from the registry
    try:
        if aws_registry is None:
            aws_registry = DevicesRegistryFactory.create(
                provider_name=DevicesRegistryType.AwsIotCoreRegistry,
                config={}
            )
        device_info = aws_registry.get_device(device_id=device_id)
        _ = device_info.pop("ResponseMetadata",None)    # ResponseMetadata can be helpful but will be just removed for now
    except Exception as e:
        _top_logger.error(f"telemetry_ds_for_deviceid: FAIL to collect info for device {device_id} with exception {e}")
        raise RuntimeError("FAIL to collect device info")

    _top_logger.debug(f"telemetry_ds_for_deviceid: Will check group name for response {device_info}")
    if isinstance(things_group_name,str) and isinstance(device_info.get("billingGroupName", None),str):
        # check if access to this device info is expected
        if things_group_name != device_info["billingGroupName"]:
            _top_logger.error(f"collect_device_info: FAIL to collect info for device {device_id} as group name is incorrect")
            raise ValueError("Cannot access device info for the group")

    # we have device info collected so we can assemble key prefix
    # expected device_info format is
    # {
    #     'defaultClientId': 'string',
    #     'thingName': 'string',
    #     'thingId': 'string',
    #     'thingArn': 'string',
    #     'thingTypeName': 'string',
    #     'attributes': {
    #         'string': 'string'
    #     },
    #     'version': 123,
    #     'billingGroupName': 'string'
    # }
    device_attrs = device_info.get("attributes", {})
    key_prefix = key_prefix.replace("{{ building_id }}", device_attrs.get("building_id", ""))
    key_prefix = key_prefix.replace("{{ location_id }}", device_attrs.get("location_id", ""))
    key_prefix = key_prefix.replace("{{ things_group_name }}", things_group_name)
    key_prefix = key_prefix.replace("{{ thing_type }}", device_info.get("thingTypeName",""))
    key_prefix = key_prefix.replace("{{ thing_name }}", device_id)
    # last step for prefix - we need to drop any timestamp related key parts
    key_prefix = "/".join([v for v in key_prefix.split("/") if not "timestamp()" in v])
    _top_logger.debug(f"telemetry_ds_for_deviceid: final key prefix for device {device_id} is {key_prefix}")
    #---------------------------------------------------------------------------

    # finally we can arrange the DataSource and add it to the "cache"
    telemetry_data_sources[device_id] = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket,
            config={
                "bucket_name": telemetry_bucket_name,
                "key_prefix": key_prefix
            }
        )

    return telemetry_data_sources[device_id]


async def collect_telemetry_objects(
        device_telemetry_ds:ObjectsDatasource,
        obj_keys:List[str],
        attributes:Union[str, List[str], None],
        label:str,
    )->List[dict]:
    ''' we need to collect and parse one telemetry object. Internal logic is 
            around "label" (what value to use for "label" key)
            around attributes - if str we'll return just that attribute value for key "value", if None - return all
    '''
    _top_logger.debug(f"collect_telemetry_objects: collect telemetry objects {obj_keys} with attributes {attributes}")
    if len(obj_keys)==0:
        return []
    try:
        telem_data:list = await device_telemetry_ds.get_objects(None, obj_keys)
    except Exception as e:
        _top_logger.error(f"collect_telemetry_objects: FAIL to collect telemetry objects {obj_keys} with exception {e}")
        return []
    _top_logger.debug(f"collect_telemetry_objects: collected {len(telem_data)} objects")
    # attrs should always be a list even when attributes is str or None
    attrs = [attributes] if isinstance(attributes,str) else (attributes or []).copy()
    # transform collected objects
    result = []
    for data_obj in telem_data:
        _top_logger.debug(f"collect_telemetry_objects: object {json.dumps(data_obj)[:15]}...")
        elem = {
            "label": data_obj.get(label,"")
        }
        if isinstance(attributes,str):
            # simple scenario
            elem["value"] = decode_data_value_by_name(data_obj.get(attributes, None), attributes)
            result.append(elem)
            continue
        elif attributes is None:
            # when attributes not provided all data_obj fields except 'label' will be added
            attrs.extend([k for k in data_obj.keys() if k!=label])
            attrs = list(set(attrs))
        elem = {
            **{k:decode_data_value_by_name(v,k) for k,v in data_obj.items()}
            **elem
        }
        result.append(elem)
    # finally - update all elements by adding None for not-available attributes
    # and converting label to string
    if isinstance(attributes, str):
        result = [ {"label":str(v["label"]), "value":v["value"]} for v in result]
    else:
        result = [
            {
                **{k:None for k in attrs},
                **v
            } for v in result
        ]
    return result


async def collect_telemetry_for_device(
        *,
        device_telemetry_ds:ObjectsDatasource,
        attributes:Union[str, List[str], None],
        label:str="mqtt_timestamp",
        user_groups:str=None,
        **kwargs
    )->List[dict]:
    ''' 
        return list of objects with ALL telemetry data available
        depending from attributes/label value object will have different formats
        1. attributes is str
        each object in the list has format like this:
        {
            "label": <string with timestamp or other field value>,
            "value": attribute value in correct format
        }
        2. attributes is List[str] or None (None will return ALL attributes)
        each object in the list has format like this:
        {
            "label": <string with timestamp or other field value>,
            "attribute_name": attribute value in correct format
        }
    '''
    result = []
    tlm_objects = None
    try:
        # first - we need to identify telemetry sources for aggregation
        tlm_objects = device_telemetry_ds.list_objects()
        # split all objects into reasonable number of loading groups
        number_of_concurrent_loads = 5
        chunk_size = len(tlm_objects)//number_of_concurrent_loads
        # create a set of coroutines where each one aggregate one group
        collect_data_tasks = [
            collect_telemetry_objects(
                device_telemetry_ds, 
                tlm_objects[i:i+chunk_size],
                attributes,
                label,
            ) for i in range(0,len(tlm_objects),chunk_size)]
        # collect each objects group
        _top_logger.info(f"collect_telemetry_for_device: start {len(collect_data_tasks)} tasks to collect data")
        collect_data_result = await asyncio.gather(*collect_data_tasks)
        _top_logger.info(f"collect_telemetry_for_device: data collected with result len {len(collect_data_result) if isinstance(collect_data_result, list) else -1}")
        _top_logger.debug(f"collect_data_result:\n{json.dumps(collect_data_result)}")
        result = [x for l in collect_data_result for x in l]
        _top_logger.debug(f"result:\n{json.dumps(result)}")
    except Exception as e:
        _top_logger.error(f"collect_telemetry_for_device: FAIL to collect telemetry objects {tlm_objects} with exception {e}")
        result = []
    
    return result


@aws_common_headers()
def lambda_handler(event:dict, context):
    ''' AWS Lambda entry point. Transform event and context to consumable by microservice_logic 
    details on event parameter can be found at:
    - https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-concepts.html#gettingstarted-concepts-event
    - https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html#apigateway-example-event
    - https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html
    - https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html
    - https://docs.aws.amazon.com/lambda/latest/dg/lambda-services.html (see event info for each service)

    details on context parameter can be found at:
    - https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
    - https://github.com/aws/aws-lambda-python-runtime-interface-client/blob/main/awslambdaric/lambda_context.py 
    '''

    try:
        # This can be extremely useful for understanding of AWS specific parameters
        _top_logger.debug(f"lambda_handler: event type: {type(event)}, context type: {type(context)}")
        _top_logger.debug(f"lambda_handler: event: {event}")
        _top_logger.debug(f"lambda_handler: context: {context}")
        _top_logger.debug(f"lambda_handler: context vars: {vars(context)}")
        # _top_logger.debug(f"lambda_handler ENVironment variables: {os.environ}") # logging all env vars can expose sensitives
        _top_logger.debug(f"lambda_handler: event json: {json.dumps(event, indent=2)}")
    except Exception as e:
        _top_logger.debug(f"lambda_handler: Exception: {e}")

    handler_loop = asyncio.new_event_loop()
    try:
        device_id = event["pathParameters"]["device_id"]
        telemetry_bucket_name = event["stageVariables"]["telemetry_bucket_name"]
        things_group_name = event["stageVariables"]["things_group_name"]
        telemetry_topic:str = os.environ.get("telemetry_topic") # telemetry topic is environment var as it's not needed by most Lambdas
        telemetry_key:str = os.environ.get("telemetry_key") # telemetry key is environment var as it's not needed by most Lambdas
        telemetry_ingest_rule_prefix = os.environ.get("telemetry_ingest_rule_prefix",None)
        user_groups = event.get("requestContext",{}).get("authorizer",{}).get("claims",{}).get("cognito:groups", None)
        req_datapoints = event.get("queryStringParameters",{}).get("values", "").split(",")
        req_format = event.get("queryStringParameters",{}).get("format", None)
        req_attributes = None
        if len(req_datapoints)>0:
            req_attributes = req_datapoints[0] if req_format in ["line", "bar", "gauge"] else req_datapoints

        # 1. Datasource for telemetry (to get the data and removed handled data)
        telem_datasource = telemetry_ds_for_deviceid(
            telemetry_bucket_name=telemetry_bucket_name,
            device_id=device_id, telemetry_key=telemetry_key, telemetry_topic=telemetry_topic,
            user_groups=user_groups, things_group_name=things_group_name,
            telemetry_ingest_rule_prefix=telemetry_ingest_rule_prefix
        )
        # 2. Invoke telemetry collection
        # total number of telemetry objects can be quite large so we'll try to do it async
        #device_telemetry_ds.get_objects()
        # handler_loop = asyncio.get_event_loop()
        telemetry_data:list = handler_loop.run_until_complete(
            collect_telemetry_for_device(
                device_telemetry_ds=telem_datasource,
                attributes=req_attributes,                    
                user_groups=user_groups,
            )
        )
        if not handler_loop.is_closed():
            handler_loop.close()

        result = {
            "statusCode": 200,
            "isBase64Encoded": False,
            "body": json.dumps(telemetry_data)
        }

    except Exception as e:
        payload = "ERROR: incorrect context"
        _top_logger.error(payload)
        _top_logger.error(f"Exception: {e}")
        if not handler_loop.is_closed():
            handler_loop.close()

        return {
            "statusCode": 400,
            "body": payload
        }

    # #! ----- M O C K ------
    # result["body"] = json.dumps([
    #     {
    #         'label': f"1683599846{i:03d}",
    #         'value': 42.22 + i*333
    #     }
    #     for i in range(0,10)
    # ])
    
    return result
