'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
import json
import logging
import os

# this is import from layer!
# NOTE that we don't include layer to Lambda deployment package
# instead it's deployed separately and made available for Lambdas (see cloud_iot_diy_cloud/cloud_iot_diy_cloud_stack.py)
if os.environ.get("AWS_LAMBDA_FUNCTION_VERSION", None) is None:
    # this part is required for local debugging only!
    import sys
    sys.path.append("./src")

from _api_handlers_common import aws_common_headers
from _objects_datasource import ObjectsDatasource, ObjectsDatasourceFactory, ObjectsDatasourceType

# logging level can/will be redefined in any specific Cloud (Lambda/Azure function/etc.)
# predefined here for local
_root_logger = logging.getLogger()
_root_logger.setLevel(level=logging.INFO)
# instantiate _top_logger to be used in this code
_top_logger = logging.getLogger(__name__)

def update_by_id_for_deviceid(
        *,
        device_id:str,
        update_id:str,
        updates_ds:ObjectsDatasource,
        **kwargs
    )->dict:
    ''' 
        returns object representing specific update
        return dict with update encoded to string for the key "data"
    '''
    if not isinstance(device_id, str) or len(device_id)==0 or not isinstance(updates_ds, ObjectsDatasource) or \
       not isinstance(update_id, str) or len(update_id)==0:
        _top_logger.error(f"update_by_id_for_deviceid: wrong parameters provided to collect dashboard")
        return {"data": ""}

    try:
        return {
            "data": updates_ds.get_blob(f"{device_id}/{update_id}")
        }
    except Exception as e:
        _top_logger.error(f"update_by_id_for_deviceid: FAIL to collect update {update_id} for device {device_id} with exception {e}")
        return {"data": ""}

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
        update_id = event["pathParameters"]["update_id"]
        # create a Datasource
        # NOTE that we're relying on stage variables!
        updates_bucket_name = event["stageVariables"]["service_bucket_name"]
        updates_key_prefix = event["stageVariables"]["updates_prefix"]
        # Datasource for dashboards
        updates_ds_s3 = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket,
            config={
                "bucket_name": updates_bucket_name,
                "key_prefix": updates_key_prefix
            }
        )

    except Exception as e:
        payload = "ERROR: incorrect context"
        _top_logger.error(payload)
        _top_logger.error(f"Exception: {e}")

        return {
            "statusCode": 400,
            "body": payload
        }

    result = {
        "statusCode": 200,
        "body": json.dumps(update_by_id_for_deviceid(device_id=device_id, update_id=update_id, updates_ds=updates_ds_s3, **event)),
        "isBase64Encoded": False
    }
    return result
