'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
import json
import logging
import os
from urllib.parse import unquote

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

def users_dashboard_by_id(
        dashboard_id:str,
        *,
        userid:str,
        dashboards_ds:ObjectsDatasource,
        **kwargs
    )->dict:
    ''' 
        returns object representing specific dashboard available for the user
        for now this is simple implementation without respect for 'shared' dashboards
        return dict with dashboard info
    '''
    if not isinstance(userid, str) or len(userid)==0 or not isinstance(dashboards_ds, ObjectsDatasource) or \
       not isinstance(dashboard_id, str) or len(dashboard_id)==0:
        _top_logger.error(f"users_dashboard_by_id: wrong parameters provided to collect dashboard")
        return {}

    try:
        return dashboards_ds.get_object(dashboard_id) or {}
    except Exception as e:
        _top_logger.error(f"users_dashboard_by_id: FAIL to collect dashboard {dashboard_id} for {userid} with exception {e}")
        return {}

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
        dashboard_id = unquote(event["pathParameters"]["dashboard_id"])
        # this way of collecting user_id is COGNITO SPECIFIC
        # if custom authorizer will be used collection of user_id will depend from Authorizer Context
        user_id = event.get("requestContext",{}).get("authorizer",{}).get("claims",{}).get("sub","")
        # create a Datasource
        # NOTE that we're relying on stage variables!
        dashboards_bucket_name = event["stageVariables"]["dashboards_bucket_name"]
        dashboards_key_prefix = event["stageVariables"]["saved_dashboards_prefix"]
        # Datasource for dashboards
        dashboards_ds_s3 = ObjectsDatasourceFactory.create(
            provider_name=ObjectsDatasourceType.S3Bucket,
            config={
                "bucket_name": dashboards_bucket_name,
                "key_prefix": f"{dashboards_key_prefix}/{user_id}"
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
        "body": json.dumps(users_dashboard_by_id(dashboard_id, userid=user_id, dashboards_ds=dashboards_ds_s3, **event)),
        "isBase64Encoded": False
    }
    return result
