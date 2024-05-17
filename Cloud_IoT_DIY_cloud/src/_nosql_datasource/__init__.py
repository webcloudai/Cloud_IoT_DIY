'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License

Abstract class (Interface definition) for NoSql datasources implementation 
'''
from abc import ABC, abstractmethod
from importlib import import_module
from typing import Union, Dict, Any
from enum import Enum
import json
import logging

class NoSqlDatasourceType(Enum):
    DynamoDb="DynamoDb"
    FileDb="FileDb"

class NoSqlDatasource(ABC):
    ''' Abstract class defining interface for different NoSql datasources 
        NOTE that document id can be a string (simple primary key) or Dict
        If the document id is a Dict it should be of format {key_name: key_value}
        key_value must be of supported types!
    '''
    
    @abstractmethod
    def add_docs(self, *, docs:list):
        ''' add documents to the NoSqlDatasource from list of tuples of format (document_id, document:dict) 
            NOTE: existing documents with same id will be replaced!'''
        pass

    @abstractmethod
    def add_one_doc(self, *, doc:tuple):
        ''' add one document to the NoSqlDatasource from tuple of format (document_id, document:dict) 
            NOTE: existing document with same id will be replaced!'''
        pass

    @abstractmethod
    def update_one_doc(self, *, doc:tuple):
        ''' document in the NoSqlDatasource will be updated or added from tuple of format (document_id, document:dict) 
            NOTE: existing document properties with same name will be replaced!'''
        pass

    @abstractmethod
    def delete_one_doc(self, *, doc_id:Union[str,Dict[str,Any]]):
        ''' delete one document from the NoSqlDatasource 
            NOTE: existing document will be removed!'''
        pass

    @abstractmethod
    def update_one_doc_properties(self, *, doc_id:Union[str,Dict[str,Any]], props:dict):
        ''' update one document with properties and values from props ''' 
        pass
    
    @abstractmethod
    def serialize(self)->dict:
        ''' serialize document db to dict '''
        pass

    @abstractmethod
    def deserialize(self, source:dict):
        ''' deserialize document db from dict '''
        pass

    @abstractmethod
    def doc_by_id(self, *, doc_id:Union[str,Dict[str,Any]])->dict:
        ''' get document with specified id from the document db. Index "[]" operator can also be used '''
        pass

    @abstractmethod
    def query_by_value(self, *, 
            doc_values:Dict[str,Any], 
            doc_id:Dict[str,Any]=None, 
            limit:int=None, start_from:Union[str,Dict[str,Any]]=None,
            native_options:Any=None
        ) -> list:
        ''' Get documents with same key/values and primary key from the document db. Returns a List '''
        pass

    @abstractmethod
    def scan_and_filter(self, *, 
            doc_values:Dict[str,Any], 
            doc_id:Dict[str,Any], 
            limit:int=None, start_from:Union[str,Dict[str,Any]]=None,
            native_options:Any=None
        ) -> list:
        ''' Get documents with same key/values from the document db using ineffective scan. Returns a List '''
        pass

    @property
    @abstractmethod
    def config(self):
        ''' read only property to get config info '''
        pass

    @abstractmethod
    def _clean(self):
        ''' clean object including graph_id, graph itself and other instance properties '''
        pass
   
    @abstractmethod
    def _save(self, option="json"):
        ''' save document db to the local filesystem in desired format (pickle, json, tsv) '''
        pass

    @abstractmethod
    def _load(self, option="json"):
        ''' load document db from the local filesystem in desired format (pickle, json, tsv)Db '''
        pass

    # this is not 100% clean (abstract class should not have non-abstract methods)
    # but really convenient as this is common properties and operators reload
    @property
    def _primary_key(self):
        ''' returns predefined name of the "id" field in some representations '''
        return "doc_id"

    @property
    def _logger(self):
        return logging.getLogger(__name__)

    @staticmethod
    def str_id(doc_id:Union[str,Dict[str,Any]])->str:
        if isinstance(doc_id, str):
            return doc_id
        if not isinstance(doc_id, dict):
            raise ValueError(f"Document Id MUST be string or dict. {doc_id} was provided.")
        # we'll transform dict into meaningful yet unique and compatible string
        return '_'.join([f"{k}-{v}" for k,v in doc_id.items()])

    def __str__(self):
        return json.dumps(self.serialize())

    def __getitem__(self, k):
        ''' This will support:
        [doc_id]                    returns document by id
        [{field_name:value, ...}]   returns document by composite id
        [(field_name,value)]        returns list of documents where field_name exists and has value
        '''
        if isinstance(k,tuple):
            return self.query_by_value(doc_values={k[0]:k[1]})
        # if isinstance(k, dict):
        #     return self.query_by_value(doc_values=k)
        return self.doc_by_id(doc_id=k)

    # def __call__(self, k):
    #     ''' This will support:
    #     (doc_id)                    returns document by id
    #     ((field_name,value))        returns list of documents where field_name exists and has value
    #     ({field_name:value, ...})   returns list of documents where at least one field_name exists and has value
    #     '''
    #     if isinstance(k,tuple):
    #         return self.query_by_value(doc_values={k[0]:k[1]})
    #     if isinstance(k, dict):
    #         return self.query_by_value(doc_values=k)
    #     return self.doc_by_id(doc_id=str(k))

    def __contains__(self, item_id:Union[str,Dict[str,Any]])->bool:
        ''' check existence of document in document db '''
        try:
            return (len(self.doc_by_id(doc_id=item_id)) != 0)
        except:
            return False

    def __eq__(self, other):
        return str(self) == str(other)
        

class NoSqlDatasourceFactory():
    ''' Factory class for generation Data Sources (NoSqlDatasource implementations)'''
    ''' NOTE: Data Sources MUST be in the same folder and file name should be the name of classes'''
    @staticmethod
    def create(*, provider_name:Union[str,NoSqlDatasourceType], config:dict)->NoSqlDatasource:
        provider_module = import_module(f"{globals()['__name__']}.{provider_name}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        return res_obj

    @staticmethod
    def create_from_dict(*, provider_name:Union[str,NoSqlDatasourceType], config:dict, serialized:dict)->NoSqlDatasource:
        provider_module = import_module(f"{globals()['__name__']}.{provider_name}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        res_obj.deserialize(serialized)
        return res_obj

    @staticmethod
    def create_from_file(*, provider_name:Union[str,NoSqlDatasourceType], config:dict, option="graphml")->NoSqlDatasource:
        provider_module = import_module(f"{globals()['__name__']}.{provider_name}")
        provider_class = getattr(provider_module, provider_name if isinstance(provider_name, str) else provider_name.value)
        res_obj = provider_class(config)
        res_obj.load(option=option)
        return res_obj

