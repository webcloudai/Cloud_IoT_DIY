'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from typing import Tuple, Dict, List
import json
import logging
import os
import asyncio
import re

# logging level can/will be redefined in any specific Cloud (Lambda/Azure function/etc.)
# predefined here for local
_root_logger = logging.getLogger()
_root_logger.setLevel(level=logging.INFO)
# instantiate _top_logger to be used in this code
_top_logger = logging.getLogger(__name__)

# this is import from layer!
# NOTE that we don't include layer to Lambda deployment package
# instead it's deployed separately and made available for Lambdas (see cloud_iot_diy_cloud/cloud_iot_diy_cloud_stack.py)
if os.environ.get("AWS_LAMBDA_FUNCTION_VERSION", None) is None:
    # this part is required for local debugging only!
    import sys
    sys.path.append("./src")
from _objects_datasource import ObjectsDatasource, ObjectsDatasourceFactory, ObjectsDatasourceType

async def aggregate_group(
        telemetry_ds:ObjectsDatasource,
        history_ds:ObjectsDatasource,
        history_obj_key:str,
        objects_to_group:List[str]
    )->bool:
    ''' 
    collect objects_to_group records from telemetry_ds and add them to history_ds/history_obj_key
    return True when aggregation successful
    '''
    # Collect telemetry
    try:
        in_data:list = await telemetry_ds.get_objects(None, objects_to_group)
    except Exception as e:
        _top_logger.error(f"FAIL to collect telemetry for aggregation with exception {e}")
        return False

    # Collect current history
    try:
        in_history:list = history_ds.get_object(history_obj_key)
    except Exception as e:
        _top_logger.warning(f"No history found for {history_obj_key}. Will create a new one.")
        in_history = []
    
    # Really SIMPLE aggregation
    for tlm_data in in_data:
        if not isinstance(tlm_data, dict):
            continue
        in_history.append(tlm_data)
    
    # Save update history
    try:
        history_ds.put_object(history_obj_key, json.dumps(in_history))
    except Exception as e:
        _top_logger.error(f"FAIL to store updated history after aggregation with exception {e}")
        return False

    # Remove aggregated telemetry data
    try:
        cleanup_results = [telemetry_ds.remove_object(v) for v in objects_to_group]
    except Exception as e:
        _top_logger.error(f"FAIL to remove telemetry data after aggregation with exception {e}")
        return False

    return all(cleanup_results)

async def aggregate_telemetry_to_annual_history(
        telemetry_ds:ObjectsDatasource,
        history_ds:ObjectsDatasource,
        group_prefix:str,
        group_by_part:List[str]=None,   # TODO - add support for more complex grouping
        **kwargs
    )->dict:
    ''' 
        collect telemetry files available and do the aggregation with this assumptions:
        - telemetry object key (file name) is the source of group information
        - group_prefix is regex string with prefix to be used for group definition
        - OPTIONAL (NOT SUPPORTED FOR NOW) group_by_part parameter enables complex groupings - by specific part of the prefix
        return dict of format
        {
            "statusCode": 200,
            "body": { },
        }
    '''
    #! We'll ignore group_by_part for now an use just split instead of regex
    group_pos_in_split = len(group_prefix.split(")/("))-1
    # first - we need to identify telemetry sources for aggregation
    tlm_objects = telemetry_ds.list_objects()
    tlm_groups:Dict[str,List[str]] = {}
    for obj_key in tlm_objects:
        key_comp = obj_key.split("/")
        if len(key_comp)<=group_pos_in_split:
            _top_logger.info(f"{obj_key} ignored as it has incorrect key pattern")
            continue
        history_obj_key = "/".join(key_comp[:group_pos_in_split]) + "/history.json"
        tlm_groups.setdefault(history_obj_key, [])
        # tlm_groups[group_key].append("/".join(key_comp[group_pos_in_split:]))
        tlm_groups[history_obj_key].append(obj_key)
    
    # collect each sources group, run the aggregation, delete sources
    # set of coroutines where each one aggregate one group
    aggr_tasks = [aggregate_group(telemetry_ds, history_ds,k,v) for k,v in tlm_groups.items()]
    aggr_result = await asyncio.gather(*aggr_tasks)

    return {
            "statusCode": 200 if all(aggr_result) else 400,
            "body": { },
        }

def telemetry_key_grouping_components(telemetry_key:str)->Tuple[int,str]:
    ''' '''
    # we need to identify grouping prefix for annual grouping
    # this will be done by generating regex pattern
    # NOTE that it's presumed that everything after the YEAR is date specific and should be grouped
    year_affix_location = telemetry_key.find("yyyy")
    if year_affix_location ==-1 :
        raise ValueError(f"Key MUST include a year pattern of format 'yyyy' but {telemetry_key} was provided")
    meaningful_parts = telemetry_key[:year_affix_location].split("/")
    key_pattern = "/".join(["(?P<part"+f"{i:02d}"+">[^/]*)" for i,_ in enumerate(meaningful_parts[:-1])])
    key_pattern += "/(?P<year>[0-9]+)"
    return key_pattern


def lambda_handler(event:dict, context):
    ''' AWS Lambda entry point. Transform event and context to consumable by microservice_logic 
    details on event parameter can be found at:
    - https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-concepts.html#gettingstarted-concepts-event
    - https://docs.aws.amazon.com/lambda/latest/dg/services-cloudwatchevents.html
    - https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html
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
        # to successfully perform aggregation our microservice needs two data sources
        # Information about S3 buckets serving telemetry and historical data is available in environment variables
        telemetry_s3_bucket_name = os.environ.get("telemetry_bucket")
        historical_s3_bucket_name = os.environ.get("historical_bucket")
        things_group_name = os.environ.get("things_group_name")
        telemetry_key:str = os.environ.get("telemetry_key")
        grouping_key_prefix = telemetry_key_grouping_components(telemetry_key)
        # 1. Datasource for telemetry (to get the data and removed handled data)
        telem_datasource = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket,
            config={
                "bucket_name": telemetry_s3_bucket_name,
                "key_prefix": ""
            }
        )
        # 2. Datasource for historical data (to get current history and update it)
        hist_datasource = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket,
            config={
                "bucket_name": historical_s3_bucket_name,
                "key_prefix": ""
            }
        )
        # 3. Create context
        # NOTE that keys here are either logic function parameters or 
        invocation_context:dict = {
            "group_prefix": grouping_key_prefix
        }

        # Now we are ready to proceed with logic invocation
        # Our microservice logic is async so we need 
        handler_loop = asyncio.get_event_loop()
        result:dict = handler_loop.run_until_complete(
            aggregate_telemetry_to_annual_history(telem_datasource, hist_datasource, **invocation_context)
        )
        if not handler_loop.is_closed():
            handler_loop.close()

    except Exception as e:
        payload = "ERROR: incorrect context"
        _top_logger.error(payload)
        _top_logger.error(f"lambda_handler: Exception: {e}")
        return {
            "statusCode": 500,
            "body": payload
        }

    return result
