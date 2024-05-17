import json
import logging
import os

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

from _api_handlers_common import aws_common_headers
from _devices_registry import DevicesRegistry, DevicesRegistryFactory, DevicesRegistryType

def collect_devices(*,
        registry:DevicesRegistry,
        things_group_name:str=None,
        user_role:str=None,
        work_mode:dict=None,
        **kwargs
    )->dict:
    ''' 
        main execution logic here (independent from particular cloud runtime)

        return dict of format
        {
            "statusCode": 200,
            "body": { },
            "headers": { }
        }
    '''
    try:
        devices_list = registry.list_devices(devices_group=things_group_name)
    except Exception as e:
        _top_logger.error(f"collect_devices: FAIL to collect devices list with exception {e}")
        return {
                "statusCode": 500,
                "body": [],
            }

    #! TEMP SOLUTION
    return {
            "statusCode": 200,
            "body": devices_list,
        }

@aws_common_headers()
def lambda_handler(event:dict, context):
    ''' AWS Lambda entry point. Transform event and context to consumable by microservice_logic 
    details on event parameter can be found at:
    - https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-concepts.html#gettingstarted-concepts-event
    - https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html#apigateway-example-event
    - https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html
    - https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html
    - https://docs.aws.amazon.com/lambda/latest/dg/lambda-services.html (see event info for each service)
    see example event in the comments below the code
    
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
        # transform LambdaContext object to dict with injection of parameters from different sources (local configs, env vars, stage vars, parameter store...)
        # invocation_context:dict = update_lambda_context(lambda_context=context,
        #                                     lambda_event=event,
        #                                     file_name="connection_context.json",
        #                                     file_context_key="systems_context",
        #                                     # api_name="symbols",   # This parameters are available in event and context
        #                                     # method="GET",         #
        #                                     runtime="aws")
        
        stage_variables = event.get("stageVariables",{})
        query_params = event.get("queryStringParameters",{})
        aws_registry = DevicesRegistryFactory.create(
            provider_name=DevicesRegistryType.AwsIotCoreRegistry,
            config={}
        )
        user_groups = event.get("requestContext",{}).get("authorizer",{}).get("claims",{}).get("cognito:groups", None)
        invocation_context:dict = {
            **event.get("requestContext",{}), 
            **stage_variables, 
            **{
                # NOTE that things_group_name will be collected directly from stage_variables
                "registry": aws_registry,
                "work_mode": query_params,
                "user_role": user_groups[0] if isinstance(user_groups,list) else user_groups,
            }
        }
        
    except Exception as e:
        payload = "ERROR: incorrect context"
        _top_logger.error(payload)
        _top_logger.error(f"Exception: {e}")

        return {
            "statusCode": 400,
            "body": payload
        }

    _top_logger.debug(f"lambda_handler: invoke logic with parameters {json.dumps({k:v for k,v in invocation_context.items() if k!='registry'},indent=3)}")

    result = collect_devices(**invocation_context)
    result.setdefault("isBase64Encoded", False)
    result["body"] = json.dumps(result.get("body",{}))

    return result
