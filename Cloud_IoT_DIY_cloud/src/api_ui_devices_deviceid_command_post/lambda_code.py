import json
import logging
import os


# logging level can/will be redefined in any specific Cloud (Lambda/Azure function/etc.)
# predefined here for local
_root_logger = logging.getLogger()
_root_logger.setLevel(level=logging.INFO)
# instantiate _top_logger to be used in this code
_top_logger = logging.getLogger(__name__)

def microservice_logic(
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

    #! TEMP SOLUTION
    return {
            "statusCode": 200,
            "body": kwargs,
            # "headers": { },
            # "Content-Type": "application/json,charset=UTF-8"
        }


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
        # transform LambdaContext object to dict with injection of parameters from different sources (local configs, env vars, stage vars, parameter store...)
        # invocation_context:dict = update_lambda_context(lambda_context=context,
        #                                     lambda_event=event,
        #                                     file_name="connection_context.json",
        #                                     file_context_key="systems_context",
        #                                     # api_name="symbols",   # This parameters are available in event and context
        #                                     # method="GET",         #
        #                                     runtime="aws")
        #! TEMP SOLUTION
        invocation_context:dict = event.copy().get("requestContext",{})

    except Exception as e:
        payload = "ERROR: incorrect context"
        _top_logger.error(payload)
        _top_logger.error(f"Exception: {e}")

        return {
            "statusCode": 400,
            "body": payload
        }

    result = microservice_logic(**invocation_context)
    result.setdefault("isBase64Encoded", False)
    result["body"] = json.dumps(result.get("body",{}))
    return result
