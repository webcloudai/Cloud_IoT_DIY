'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License

ANoSqlDatasource implementation with file '''

from typing import Union, Dict, List, ByteString
from importlib import import_module
from dataclasses import dataclass
# from pathlib import Path
from urllib.parse import quote_plus, unquote_plus
import json
import logging
_top_logger = logging.getLogger(__name__)

from . import DevicesRegistry

@dataclass(eq=True, frozen=True)
class AwsIotCoreRegistryConfig:
    ''' '''

class AwsIotCoreRegistry(DevicesRegistry):
    ''' 
        DevicesRegistry implementation with local AWS IoT Core Registry
    '''
    # SOME CONSTANTS
    DELIMITER = "/"

    # dynamically loaded boto3 module
    _boto3 = None

    # Basic client
    _s3_client = None  # NOTE that boto3 clients are thread-safe

    @staticmethod
    def encode_kv(value:str)->str:
        ''' for attributes dict keys and values must confirm [a-zA-Z0-9_.,@/:#-] 
            we'll use URL encode and also replace "~"
            and finally replace "%" with "#" and "+" with "@"
        '''
        enc_v = quote_plus(value, safe="_.,/:-")
        enc_v = enc_v.replace("~", "%7E").replace("%","#").replace("+","@")
        return enc_v

    @staticmethod
    def decode_kv(value:str)->str:
        ''' for attributes dict keys and values must confirm [a-zA-Z0-9_.,@/:#-] 
            we'll replace back "#" with "%" and "@" with "+"
            we'll use URL decode and also replace "%7E" back to "~"
        '''
        dec_v = value.replace("@","+").replace("#","%").replace("%7E", "~")
        dec_v = unquote_plus(dec_v)
        return dec_v

    def __init__(self, config:dict):
        '''  '''
        # Verify that the config contains a dictionary object with required parameters
        try:
            self._config = AwsIotCoreRegistryConfig(**config)
        except Exception as e:
            _top_logger.error("Layer-AwsIotCoreRegistry: config should be a dict and has required values. Failed with exception {e}")
            raise ValueError
        try:
            self._boto3 = import_module("boto3")
            self._iot_client = self._boto3.client("iot") # NOTE that boto3 clients are thread-safe
        except Exception as e:
            _top_logger.error(f"FAIL to init AwsIotCoreRegistry registry with exception {e}")
            raise e

    def list_device_types(self)->List[str]:
        ''' list all device types in the group '''
        results = []
        continuation_token = True
        while not continuation_token is None:
            try:
                # we'll use list_thing_types
                cl_params = {
                    # "nextToken":'string',
                    "maxResults": 250   # 250 is max
                    # "attributeName": 'string',
                    # "attributeValue": 'string',
                    # "thingTypeName": 'string',
                    # "usePrefixAttributeValue": True|False
                }
                if continuation_token not in [True, None]:
                    cl_params["nextToken"] = continuation_token,
                resp = self._iot_client.list_thing_types(**cl_params)
                
                continuation_token = resp.get("nextToken", None)
                results.extend(resp.get("thingTypes",[]))
            except Exception as e:
                _top_logger.error(f"FAIL to collect device types with exception {e}")
                continuation_token = None

        return [(v["thingTypeName"] if isinstance(v,dict) else v) for v in results]

    def add_device_type(self, 
                        device_type_name:str, 
                        device_type_info:Dict[str, Union[str, List[str]]]=None,
                        device_type_tags:List[dict]=None)->bool:
        ''' add the device type to the Registry (update if exists) '''
        # we'll use create_thing_type
        try:
            cl_params = { "thingTypeName": device_type_name }
            if isinstance(device_type_info, dict):
                cl_params["thingTypeProperties"] = device_type_info
            if isinstance(device_type_tags, list):
                cl_params["tags"] = device_type_tags
            return self._iot_client.create_thing_type( **cl_params ).get("thingTypeName",None) == device_type_name
        except Exception as e:
            _top_logger.error(f"FAIL to add device type {device_type_name} with exception {e}")
        return False

    def list_devices(self, devices_group:str=None)->List[str]:
        ''' list all devices in the group '''
        results = []
        continuation_token = True
        while not continuation_token is None:
            try:
                if isinstance(devices_group, str):
                    # we'll need to use list_things_in_thing_group
                    cl_params = {
                        "thingGroupName": devices_group,
                        "recursive": True,
                        # nextToken='string',
                        "maxResults": 250   # 250 is max
                    }
                else:
                    # we'll use list_things
                    cl_params = {
                        # "nextToken":'string',
                        "maxResults": 250   # 250 is max
                        # "attributeName": 'string',
                        # "attributeValue": 'string',
                        # "thingTypeName": 'string',
                        # "usePrefixAttributeValue": True|False
                    }
                if continuation_token not in [True, None]:
                    cl_params["nextToken"] = continuation_token,
                resp = self._iot_client.list_things_in_thing_group(**cl_params) if isinstance(devices_group, str) else self._iot_client.list_things(**cl_params)
                
                continuation_token = resp.get("nextToken", None)
                results.extend(resp.get("things",[]))
            except Exception as e:
                _top_logger.error(f"FAIL to collect devices in group {devices_group} with exception {e}")
                continuation_token = None

        return [(v["thingName"] if isinstance(v,dict) else v) for v in results]

    def get_device(self, device_id:str)->dict:
        ''' get the device info '''
        try:
            resp = self._iot_client.describe_thing( thingName=device_id )
            resp_attrs = {}
            for k,v in resp.get("attributes",{}).items():
                attr_name = AwsIotCoreRegistry.decode_kv(k)
                attr_v = AwsIotCoreRegistry.decode_kv(v)
                try:
                    resp_attrs[attr_name] = json.loads(attr_v)
                except:
                    resp_attrs[attr_name] = attr_v
            resp["attributes"] = resp_attrs
        except Exception as e:
            _top_logger.error(f"FAIL to collect device info for device {device_id} with exception {e}")
            resp = None
        return resp or {}

    def update_device(self, device_id:str, device_info:dict, device_type:str=None)->bool:
        ''' update existing device with device_info '''
        ''' per boto3 docs:
            response = client.update_thing(
                thingName='string',
                thingTypeName='string',
                attributePayload={
                    'attributes': {
                        'string': 'string'
                    },
                    'merge': True|False
                },
                expectedVersion=123,
                removeThingType=True|False
            )        
        '''
        update_props = {
            "thingName": device_id,
            "removeThingType": False,
            "attributePayload": {
                "attributes": {}, # {k:str(v) for k,v in device_info.items()},
                "merge": True
            }
        }
        #! NOTE that for attributes dict
        #!  keys MUST be [a-zA-Z0-9_.,@/:#-]+] with max length of 128
        #!  values MUST be [a-zA-Z0-9_.,@/:#-]*] with max length of 800
        for k,v in device_info.items():
            attr_name = AwsIotCoreRegistry.encode_kv(k)
            if isinstance(v,str):
                update_props["attributePayload"]["attributes"][attr_name] = AwsIotCoreRegistry.encode_kv(v)
            else:
                try:
                    update_props["attributePayload"]["attributes"][attr_name] = AwsIotCoreRegistry.encode_kv(json.dumps(v))
                except Exception as e:
                    _top_logger.error(f"Value {v} for attribute {k} unserializable with exception {e} and will be ignored")
                    continue
        
        if isinstance(device_type, str):
            curr_types = self.list_device_types()
            if device_type not in curr_types:
                self.add_device_type(device_type_name=device_type)
            update_props["thingTypeName"] = device_type
        try:
            _ = self._iot_client.update_thing(**update_props)
            resp = True
        except Exception as e:
            _top_logger.error(f"FAIL to collect device info for device {device_id} with exception {e}")
            resp = False
        return resp

    def put_device(self, device_id:str, device_info:dict)->bool:
        ''' add the device to the Registry (update if exists) '''
        raise RuntimeError("NOT IMPLEMENTED")
        # get device
        # if available - update
        # else - create thing

    def remove_device(self, device_id:str)->bool:
        ''' remove (delete) the device from the Registry '''
        raise RuntimeError("NOT IMPLEMENTED")

    def query_devices(self, meta_data_query:dict)->List[str]:
        ''' query devices by metadata from the Registry '''
        raise RuntimeError("NOT IMPLEMENTED")
