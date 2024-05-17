'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
#! NOTE that specific implementations of abstract ObjectsDatasource class may require additional modules
#! This is a responsibility of consuming service to install required dependencies!
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Union, Dict, List, ByteString
from enum import Enum
import json
import logging
_top_logger = logging.getLogger(__name__)

class ObjectsDatasourceType(Enum):
    S3Bucket="S3Bucket"
    LocalFolder="LocalFolder"


class ObjectsDatasource(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def list_objects(self, prefix:str=None, filter:str=None)->List[str]:
        ''' list all objects in the Datasource 
            NOTE that you can use EITHER prefix OR filter but not both
        '''

    @abstractmethod
    def get_blob(self, key:str)->ByteString:
        ''' get the blob from the Datasource '''

    @abstractmethod
    async def get_objects(self, filter:str, keys:List[str], encoding:str="utf-8", format:str="json")->List[Union[str, Dict, List]]:
        ''' get all objects from the Datasource '''

    @abstractmethod
    def put_object(self, key:str, obj:Union[str, ByteString], encoding:str="utf-8")->bool:
        ''' add the object to the Datasource (replace if exists) '''

    @abstractmethod
    def remove_object(self, key:str)->bool:
        ''' remove (delete) the object from the Datasource '''

    @abstractmethod
    async def remove_objects(self, filter:str)->List[bool]:
        ''' remove/delete multiple objects from the Datasource '''

    @abstractmethod
    def query_objects(self, meta_data_query:dict)->List[str]:
        ''' query objects by metadata in the Datasource '''

    # NON-ABSTRACT COMMON METHODS
    # not clean abstract class but more effective to code and use   

    def get_object(self, key:str, encoding:str="utf-8", format:str="json")->Union[ByteString, str, Dict, List]:
        ''' get the object from the Datasource '''
        res = self.get_blob(key)
        if isinstance(encoding, str):
            res = res.decode(encoding)
            match format:
                case "json":
                    res = json.loads(res)
        return res

    async def get_blobs(self, filter:str, keys:List[str])->List[ByteString]:
        ''' get all blobs in the Datasource '''
        return await self.get_objects(filter, keys, None, None)


class ObjectsDatasourceFactory():
    ''' 
    Factory class for generation Data Sources (ObjectsDatasource implementations)
    NOTE: Data Sources MUST be in the same folder and file name should be the name of classes
    '''
    @staticmethod
    def create(*, provider_name:Union[str,ObjectsDatasourceType], config:dict)->ObjectsDatasource:

        provider_module = import_module(f"{globals()['__name__']}.{provider_name if isinstance(provider_name, str) else provider_name.value}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        return res_obj

    @staticmethod
    def create_from_dict(*, provider_name:Union[str,ObjectsDatasourceType], config:dict, serialized:dict)->ObjectsDatasource:
        provider_module = import_module(f"{globals()['__name__']}.{provider_name if isinstance(provider_name, str) else provider_name.value}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        res_obj.deserialize(serialized)
        return res_obj

    @staticmethod
    def create_from_file(*, provider_name:Union[str,ObjectsDatasourceType], config:dict, option="graphml")->ObjectsDatasource:
        provider_module = import_module(f"{globals()['__name__']}.{provider_name if isinstance(provider_name, str) else provider_name.value}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        res_obj.load(option=option)
        return res_obj

