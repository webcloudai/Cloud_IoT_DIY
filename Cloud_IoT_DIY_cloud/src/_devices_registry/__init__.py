'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
#! NOTE that specific implementations of abstract DevicesRegistry class may require additional modules
#! This is a responsibility of consuming service to install required dependencies!
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Union, Dict, List
from enum import Enum
import logging
_top_logger = logging.getLogger(__name__)

class DevicesRegistryType(Enum):
    AwsIotCoreRegistry="AwsIotCoreRegistry"

class DevicesRegistry(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def list_device_types(self)->List[str]:
        ''' list all device types in the group '''

    @abstractmethod
    def add_device_type(self, 
                        device_type_name:str, 
                        device_type_info:Dict[str, Union[str, List[str]]]=None,
                        device_type_tags:List[dict]=None)->List[str]:
        ''' add the device type to the Registry (update if exists) '''

    @abstractmethod
    def list_devices(self, devices_group:str=None)->List[str]:
        ''' list all devices in the group '''

    @abstractmethod
    def get_device(self, device_id:str)->dict:
        ''' get the device info 
            NOTE that json-deserialization attempt will be executed for all "attributes" values!
        '''

    # @abstractmethod
    # async def get_devices(self, filter:str, device_ids:List[str], encoding:str="utf-8", format:str="json")->List[Union[str, Dict, List]]:
    #     ''' get all devices info from the Registry '''

    @abstractmethod
    def put_device(self, device_id:str, device_info:Dict[str,str])->bool:
        ''' add the device to the Registry (update if exists) 
            NOTE that device_info values MUST be strings or json-serializable objects!
        '''

    @abstractmethod
    def update_device(self, device_id:str, device_info:Dict[str,str], device_type:str=None)->bool:
        ''' update existing device with device_info 
            NOTE that device_info values MUST be strings or json-serializable objects!
        '''

    @abstractmethod
    def remove_device(self, device_id:str)->bool:
        ''' remove (delete) the device from the Registry '''

    # @abstractmethod
    # async def remove_devices(self, filter:str)->List[bool]:
    #     ''' remove/delete multiple devices from the Registry '''

    @abstractmethod
    def query_devices(self, meta_data_query:dict)->List[str]:
        ''' query devices by metadata from the Registry '''

    # NON-ABSTRACT COMMON METHODS
    # not clean abstract class but more effective to code and use   



class DevicesRegistryFactory():
    ''' 
    Factory class for generation Data Sources (DevicesRegistry implementations)
    NOTE: Data Sources MUST be in the same folder and file name should be the name of classes
    '''
    @staticmethod
    def create(*, provider_name:Union[str,DevicesRegistryType], config:dict)->DevicesRegistry:

        provider_module = import_module(f"{globals()['__name__']}.{provider_name if isinstance(provider_name, str) else provider_name.value}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        return res_obj

    @staticmethod
    def create_from_dict(*, provider_name:Union[str,DevicesRegistryType], config:dict, serialized:dict)->DevicesRegistry:
        provider_module = import_module(f"{globals()['__name__']}.{provider_name if isinstance(provider_name, str) else provider_name.value}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        res_obj.deserialize(serialized)
        return res_obj

    @staticmethod
    def create_from_file(*, provider_name:Union[str,DevicesRegistryType], config:dict, option="graphml")->DevicesRegistry:
        provider_module = import_module(f"{globals()['__name__']}.{provider_name if isinstance(provider_name, str) else provider_name.value}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        res_obj.load(option=option)
        return res_obj

