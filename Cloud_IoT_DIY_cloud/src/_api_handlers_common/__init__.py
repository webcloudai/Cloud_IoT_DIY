'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from functools import wraps
import uuid
from typing import Union
import json

import logging
_top_logger = logging.getLogger(__name__)

def decode_data_value_by_name(v:Union[str,None], name:str):
    ''' according to naming convention name contains info about value type '''
    if v is None or not isinstance(name, str):
        return v
    # parse name by naming convention which is
    # "<endpoint name>|<data units>|<value type>"
    name_comp = name.split("|")
    if len(name_comp)!=3:
        return v
    try:
        match name_comp[2]:
            case "int":
                return int(v)
            case "float":
                return float(v)
            case "str":
                return v
            case "bool":
                return v.lower()=="true"
            case "list" | "dict":
                return json.loads(v) if isinstance(v, str) else v
            case _:
                _top_logger.warning(f"decode_data_value_by_name: DID NOT convert value {v} for name {name}")
                return v
    except Exception as e:
        _top_logger.error("decode_data_value_by_name: FAIL to convert value {v} for name {name} with exception {e}")
        return v

def header_values(event:dict, header_name:str)->list:
    ''' parse header for list of values for header_name with check on lower case'''
    h_values = None
    try:
        headers = event["headers"]
    except:
        return None
    for h_name in [header_name, header_name.lower()]:
        # case sensitivity added for non-APIGateway implementations
        if h_name in headers and isinstance(headers[h_name], str) and len(headers[h_name])>0:
            if "," in headers[h_name]:
                h_values = [v.strip().lower() for v in str.split(headers[h_name],",")]
            else:
                h_values = [v.strip().lower() for v in  str.split(headers[h_name],";")]
            break
    
    return h_values


#=========================================================
#
# DECORATORs
#
def aws_common_headers(accept_values:list=None, extend_parameters:bool=False):
    ''' Decorator for lambda_handlers with event dictionary and context parameters!
        Expecting particular Stage Variables!
        Handles different common headers including
        CORS headers
            - for 'simple' CORS requests Lambda function (connected as proxy)
            must return ant least "Access-Control-Allow-Origin" header 

        X-Correlation-ID header
            - Reuse provided Correlation-ID or generate new one and 
            add it to the result dict with "headers" key.
        Accept header 
            - verify that request Accept header value is in the accept_values list (if provided)
            
        TODO - add "Content-Type": "application/json,charset=UTF-8"

        Correlation_id and accept_values (if available) CAN be added to api_call if extend_parameters set to True
    '''
    def actual_headers_handler(api_implementation):
        @wraps(api_implementation)
        def wrapped(*args, **kwargs):
            ''' extra wrapping required to preserve doc strings and other meta-data '''
            # try to find event dict to collect X-Correlation-ID header
            if isinstance(kwargs, dict) and "event" in kwargs:
                event = kwargs["event"]
            else:
                event = args[0]
            # check that we have event
            if not isinstance(event, dict):
                return {
                    "statusCode": 500,
                    "body": "aws_common_headers: event object failure"
                }
            # _top_logger.debug(f"aws_common_headers: event:={event}")
            # collect corelation id (potentially multiple ids)
            correlation_ids = header_values(event, "X-Correlation-ID")
            if correlation_ids == None or len(correlation_ids)==0:
                correlation_id = str(uuid.uuid4())
            elif len(correlation_ids)>1:
                correlation_id = ",".join(correlation_ids)
            elif len(correlation_ids[0]) == 0:
                correlation_id = str(uuid.uuid4())
            else:
                correlation_id = correlation_ids[0]
            # collect Accept headers
            h_accept = None
            if isinstance(accept_values, list):
                h_accept = header_values(event, "Accept")
                if h_accept != None and len(h_accept) > 0 and (not "*/*" in h_accept):
                    # check if expected Content-Type is right
                    accept_values_lower = [v.lower() for v in accept_values]
                    unexpected_accept = [v for v in h_accept if v.lower() not in accept_values_lower]
                    if len(unexpected_accept) > 0 :
                        # this effectively means that we have part of Accept header which is not supported
                        return {
                            "statusCode": 406,
                            "body": f"aws_common_headers: {', '.join(unexpected_accept)} is not supported"
                        }
            # CORS headers
            #* NOTE that CORS values expected to be in stage variable of event
            #* NOTE that value for the variable expected to be is particular format!
            # _top_logger.debug(f"aws_common_headers: event= {event}")
            origins = event.get("stageVariables",{}).get("AccessControlAllowOrigin","").replace("&&:&&","*")
            cors_headers = {
                **{
                    v:"["+event.get("stageVariables",{}).get(v.replace("-",""),"").replace("&&:&&","*")+"]"
                    for v in [
                        # "Access-Control-Allow-Methods",
                        # "Access-Control-Allow-Headers",
                    ]
                },
                **{
                    "Access-Control-Allow-Origin": 
                        origins if len(origins.split(","))==1 else [origins],
                    "Access-Control-Allow-Credentials": False 
                        if event.get("stageVariables",{}).get("AccessControlAllowCredentials","true").lower()=="false"
                        else True
                }
            }
            _top_logger.debug(f"aws_common_headers: cors_headers= {cors_headers}")

            # try to execute api handler
            if kwargs == None:
                kwargs = {}
            if extend_parameters:
                kwargs.setdefault("correlation_id", correlation_id)
                if h_accept != None:
                    # add accept_values only if provided
                    kwargs.setdefault("accept_values", h_accept)
            try:
                result = api_implementation(*args, **kwargs)
            except Exception as e:
                _top_logger.error(f"aws_common_headers: Exception:\n{e}")
                result = {
                    "statusCode": 500,
                    "body": "aws_common_headers: API failure"
                }
            # add correlation id to the function result
            result.setdefault("headers", {})
            # we'll not replace the correlation id if provided
            result["headers"].setdefault("X-Correlation-ID", correlation_id)
            result["headers"] = {**result["headers"], **cors_headers}
            # _top_logger.debug(f"aws_common_headers: result= {result}")

            return result

        return wrapped
    return actual_headers_handler
