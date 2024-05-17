'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
import json
import logging
import os
import asyncio
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
_root_logger.setLevel(level=logging.DEBUG)
# instantiate _top_logger to be used in this code
_top_logger = logging.getLogger(__name__)

# define some global variables to benefit from Lambda "hot start"
historical_data_sources:Dict[str, ObjectsDatasource] = {}
aws_registry:DevicesRegistry = None

def historical_ds_for_deviceid(historical_bucket_name:str, device_id:str,
                              historical_key:str,
                              user_groups:str=None,
                              things_group_name:str=None,
                              historical_ingest_rule_prefix:str=None)->ObjectsDatasource:
    ''' collect from cache or generate a new DataSource '''
    global historical_data_sources, aws_registry

    if device_id in historical_data_sources:
        return historical_data_sources[device_id]

    # we need to find the right prefix for this device_id datasource
    # we know that the key can have a rule in the name (if basic ingest is used)
    key_prefix = historical_key
    if historical_key.startswith("$aws/rules/"):
        # basic ingest is used so we need to remove rule prefix
        key_prefix = "/".join(historical_key.split("/")[3:])
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
        _top_logger.error(f"historical_ds_for_deviceid: FAIL to collect info for device {device_id} with exception {e}")
        raise RuntimeError("FAIL to collect device info")

    _top_logger.debug(f"historical_ds_for_deviceid: Will check group name for response {device_info}")
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
    _top_logger.debug(f"historical_ds_for_deviceid: final key prefix for device {device_id} is {key_prefix}")
    # finally we can arrange the DataSource and add it to the "cache"
    historical_data_sources[device_id] = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket,
            config={
                "bucket_name": historical_bucket_name,
                "key_prefix": key_prefix
            }
        )

    return historical_data_sources[device_id]


async def collect_historical_obj(
        device_historical_ds:ObjectsDatasource,
        obj_keys:List[str],
        attributes:Union[str, List[str], None],
        label:str,
    )->List[dict]:
    ''' '''
    if len(obj_keys):
        return []
    try:
        telem_data:list = await device_historical_ds.get_objects(None, obj_keys)
    except Exception as e:
        _top_logger.error(f"collect_historical_obj: FAIL to collect historical objects {obj_keys} with exception {e}")
        return []
    # transform collected objects
    attrs = (attributes or []).copy()
    result = []
    for data_obj in telem_data:
        elem = {
            "label": data_obj.get(label,"")
        }
        if isinstance(attributes,str):
            # simple scenario
            elem["value"] = decode_data_value_by_name(data_obj.get(attributes, None), attributes)
            continue
        # when attributes not provided all data_obj fields except 'label' will be added
        if attributes is None:
            attrs.extend([k for k in data_obj.keys() if k!=label])
        elem = {
            **{k:decode_data_value_by_name(v,k) for k,v in data_obj.items()}
            **elem
        }
    # finally - update all elements by adding None for not-available attributes
    if not isinstance(attributes, str):
        result = [
            {
                **{k:None for k in attrs},
                **v
            } for v in result
        ]
    return result


async def collect_historical_for_device(
        *,
        device_historical_ds:ObjectsDatasource,
        attributes:Union[str, List[str], None],
        label:str="mqtt_timestamp",
        user_groups:str=None,
        latest_year_of_interest:str=None,
        number_of_years:int=1,
        max_number_of_history_records:int=3000,
        **kwargs
    )->List[dict]:
    ''' 
        return list of objects with ALL historical data available
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
    try:
        # first - we need to identify historical sources for aggregation
        # each object has historical data for one YEAR
        hist_objects = device_historical_ds.list_objects()
        # we need to limit number of loaded years
        # TODO: latest year, number of years and number of records should be query params !!!
        hist_objects.sort(reverse=True)
        hist_objects = hist_objects[:number_of_years]
        # split all objects into reasonable number of loading groups
        number_of_concurrent_loads = max(len(hist_objects), 5)

        chunk_size = len(hist_objects)//number_of_concurrent_loads
        # create a set of coroutines where each one load one set of years
        collect_data_tasks = [
            collect_historical_obj(
                device_historical_ds, 
                hist_objects[i:i+chunk_size],
                attributes,
                label,
            ) for i in range(0,len(chunk_size),chunk_size)]
        # collect each objects group
        collect_data_result = await asyncio.gather(*collect_data_tasks)

    except Exception as e:
        _top_logger.error(f"collect_historical_for_device: FAIL to collect historical objects {hist_objects} with exception {e}")
        return []
    
    return [x for l in collect_data_result for x in l][:max_number_of_history_records]


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
        # _top_logger.debug(f"lambda_handler ENVironment variables: {os.environ}")
        _top_logger.debug(f"lambda_handler: event json: {json.dumps(event, indent=2)}")
    except Exception as e:
        _top_logger.debug(f"lambda_handler: Exception: {e}")

    try:
        device_id = event["pathParameters"]["device_id"]
        historical_bucket_name = event["stageVariables"]["historical_bucket_name"]
        things_group_name = event["stageVariables"]["things_group_name"]
        historical_key:str = os.environ.get("telemetry_topic") # telemetry topic is environment var as it's not needed by most Lambdas
        historical_ingest_rule_prefix = os.environ.get("telemetry_ingest_rule_prefix",None)
        user_groups = event.get("requestContext",{}).get("authorizer",{}).get("claims",{}).get("cognito:groups", None)
        req_datapoints = event.get("queryStringParameters",{}).get("values", "").split(",")
        req_format = event.get("queryStringParameters",{}).get("format", None)
        req_attributes = None
        if len(req_datapoints)>0:
            req_attributes = req_datapoints[0] if req_format in ["line", "bar", "gauge"] else req_datapoints

        # 1. Datasource for historical (to get the data and removed handled data)
        telem_datasource = historical_ds_for_deviceid(
            historical_bucket_name=historical_bucket_name,
            device_id=device_id, historical_key=historical_key,
            user_groups=user_groups, things_group_name=things_group_name,
            historical_ingest_rule_prefix=historical_ingest_rule_prefix
        )
        # 2. Invoke historical collection
        # total number of historical objects can be quite large so we'll try to do it async
        #device_historical_ds.get_objects()
        handler_loop = asyncio.get_event_loop()
        historical_data:list = handler_loop.run_until_complete(
            collect_historical_for_device(
                device_historical_ds=telem_datasource,
                attributes=req_attributes,                    
                user_groups=user_groups,
            )
        )
        if not handler_loop.is_closed():
            handler_loop.close()

        result = {
            "statusCode": 200,
            "isBase64Encoded": False,
            "body": json.dumps(historical_data)
        }

    except Exception as e:
        payload = "ERROR: incorrect context"
        _top_logger.error(payload)
        _top_logger.error(f"Exception: {e}")

        return {
            "statusCode": 400,
            "body": payload
        }

    #! ----- M O C K ------
    result["body"] = json.dumps([
        {
            'label': f"1683599846{i:03d}",
            'value': 42.22 + i*3
        }
        for i in range(0,1000)
    ])
    return result
