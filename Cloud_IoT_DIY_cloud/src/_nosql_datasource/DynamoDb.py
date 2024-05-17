'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License

NoSqlDatasource implementation with DynamoDb '''
from _nosql_datasource import NoSqlDatasource
import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
import decimal
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Union, Dict, Tuple

def replace_decimals(obj):
    ''' DynamoDb returns stored numbers in proprietary format decimal.Decimal 
        this function cast Decimal to Python int or float
    '''
    if isinstance(obj, list):
        for i, one_obj in enumerate(obj):
            obj[i] = replace_decimals(one_obj)
        return obj
    elif isinstance(obj, dict):
        for k in obj.keys():
            obj[k] = replace_decimals(obj[k])
        return obj
    elif isinstance(obj, decimal.Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj

class DynamoDbSubtype(Enum):
    TABLE = "table"         # DynamoDb Table
    TABLE_S3 = "table+s3"   # Table with large documents offloaded to S3
    LOCAL = "local"         # locally running DynamoDb emulator

@dataclass(eq=True, frozen=True)
class DynamoDbConfig:
    table_name:str          # - the table name provided from the config object
    subtype:Union[str,DynamoDbSubtype]  # - the subtype (aws, table+s3 or local) provided from the config object
    partition_key:str       # - the partition key of the table provided in the config object
    sort_key:str=None       # - (optional) sort key of the table provided in the config object
    region:str=None         # - the region provided from the config object
    endpoint_url:str=None   # - not required, if present in config object represents location of dynamodb
    s3_bucket_name:str=None # - (optional BUT required if subtype is table+s3) name of the bucket to offload the document
    s3_prefix:str=None      # - (optional) prefix for the offloaded documents

class DynamoDb(NoSqlDatasource):
    ''' Document Db implementation with DynamoDb and (optionally S3 Bucket)
        option _AWS_DYNAMODB_TYPE will just store document in the Table
        with _table+s3_WITH_DYNAMODB_TYPE the document will be stored in S3 bucket and limited copy will be added to the Table
            in general - only attributes with values of simple type will be stored in Table
                         all container types will be available in the S3 bucket stored document
    '''
    _MAX_NUMBER_OF_RESPONSE_PAGES_ASSEMBLED = 30
    # _AWS_DYNAMODB_TYPE = "table"
    # _table+s3_WITH_DYNAMODB_TYPE = "table_s3"
    _ddb_client = boto3.client("dynamodb")
    _s3_client = boto3.client("s3")
    

    def __init__(self, config: dict):
        ''' config must contain table_name (table must be already created), subtype, and partition_key
            see details on config parameters in DynamoDbConfig class definition
        '''
        # Verify that the config contains a dictionary object and the subtype exists
        try:
            self._config = DynamoDbConfig(**config)
        except Exception as e:
            self._logger.error("Layer-DynamoDb: config should be a dict and have at list value for 'subtype' key. Failed with exception {e}")
            raise ValueError
        
        if isinstance(self.config.table_name, str):
            self._table_name = self.config.table_name
        else:
            self._logger.error("Layer-DynamoDb: config should have a str value for 'table_name' key")
            raise ValueError

        self._type_serializer = TypeSerializer()
        self._type_deserializer = TypeDeserializer()
        self._bucket_name = None
        self._bucket_prefix = ""
        self.type:DynamoDbSubtype = self.config.subtype if isinstance(self.config.subtype, DynamoDbSubtype) else DynamoDbSubtype[self.config.subtype]
        
        if self.type in [DynamoDbSubtype.TABLE, DynamoDbSubtype.TABLE_S3, DynamoDbSubtype.LOCAL]:
            # some configuration required for DynamoDb scenario
            # we'll prepare representation of keys suitable for future use with commands
            self._partition_key = self.config.partition_key
            self._sort_key = self.config.sort_key if self.config.sort_key else None

            if self.type == DynamoDbSubtype.TABLE_S3:
                # extra configuration required for DynamoDb + S3 scenario
                try:
                    self._bucket_name = self.config.s3_bucket_name.lower()
                except Exception as e:
                    message = f"Layer-DynamoDb: Fail to collect S3 bucket name which is required for '{DynamoDbSubtype.TABLE_S3}' config type. Exception {e}"
                    self._logger.error(message)
                    raise ValueError(message)
                if isinstance(self.config.s3_prefix, str):
                    self._bucket_prefix = f"{self.config.s3_prefix}{'' if self.config.s3_prefix.endswith('/') else '/'}"
                else:
                    self._bucket_prefix =  ""

        else:
            self._logger.error("Layer-DynamoDb: Currently, only table, table+s3 or local is supported")
            raise ValueError


    @property
    def config(self)->DynamoDbConfig:
        return self._config

    def _attr_from_value(self, value:any)->Dict[str, any]:
        ''' this static method transforms the value to DynamoDb AttributeValue '''
        return self._type_serializer.serialize(value)

    def _value_from_attr(self, attr:Dict[str, any])->any:
        ''' this static method transforms the value to DynamoDb AttributeValue '''
        return self._type_deserializer.deserialize(attr)

    def _primary_key(self, doc_id:Union[str,Dict[str,any]])->Dict[str,Dict[str,any]]:
        ''' '''
        if isinstance(doc_id, str):
            return { self._partition_key: self._attr_from_value(doc_id) }
        elif isinstance(doc_id, dict):
            return { k:self._attr_from_value(v) for k,v in doc_id.items() }
        message = f"Layer-DynamoDb-add_one_doc: doc_id must be either str or dict. {doc_id} provided"
        self._logger.error(message)
        raise ValueError(message)
        
    def _s3_key_for_docid(self, doc_id)->str:
        ''' standardized key for documents offloaded to the S3 bucket '''
        return f"{self._bucket_prefix}{self.str_id(doc_id)}.json"

    def _expr_attr_names_values_for(self, 
            item:Dict[str, any],
            prefix:str="a",
        )->Tuple[Dict[str,str],Dict[str,Dict[str,any]]]:
        ''' transform object into two dicts according to DynamoDb client requirements '''
        attr_names:Dict[str,str] = {}
        attr_values:Dict[str,Dict[str,any]] = {}
        for i,(a_name,a_value) in enumerate(item.items()):
            repl_name = f":{prefix}{i:03d}"
            attr_names[repl_name] = a_name
            attr_values[repl_name] = self._attr_from_value(a_value)
        
        return (attr_names, attr_values)



    def update_one_doc(self, *, doc:tuple):
        ''' document in the NoSqlDatasource will be updated or added from tuple of format (document_id, document:dict) 
            NOTE: existing document with same id will be replaced!'''
        raise RuntimeError(f"Layer-DynamoDb-update_one_doc: Not supported for now")

    def add_docs(self, *, docs:list):
        ''' add documents to the NoSqlDatasource from list of tuples of format (document_id, document:dict) 
            NOTE: existing documents with same id will be replaced!'''
        # Loop thru list of tuples and call add_one_doc
        for one_doc in docs:
          self.add_one_doc(doc=one_doc)

    def add_one_doc(self, *, doc: tuple):
        ''' add one document to the NoSqlDatasource from tuple of format (document_id, document:dict) 
        NOTE: existing document with same id will be replaced!'''
        # Init a dictionary pointing to the second object in the tuple
        if not isinstance(doc, (tuple, list)) or len(doc)!=2 or doc[0] is None or doc[1] is None:
            message = f"Layer-DynamoDb-add_one_doc: Document ID and Document data should not be none and be elements of tuple! Document provided: {doc}"
            self._logger.error(message)
            raise ValueError(message)
        if not isinstance(doc[1], dict):
            message = f"Layer-DynamoDb-add_one_doc: Document data should be dict! Document data provided: {doc[1]}"
            self._logger.error(message)
            raise ValueError(message)

        try:
            item = deepcopy(doc[1])
        except Exception as e:
            self._logger.warning(f"Layer-DynamoDb-add_one_doc: FAIL to deepcopy provided document with exception {e}. Original will be used but this may affect overall behavior.")
            item = doc[1]

        # Add the primary key to the dictionary - THIS CAN AFFECT SOURCE DOCUMENT IF DEEPCOPY FAILS !
        # item.update({self._primary_key : doc[0]})

        # fow table+s3 we need to store the document in the S3 bucket
        if self.type == DynamoDbSubtype.TABLE_S3:
            doc_key = self._s3_key_for_docid(doc[0])
            bckt_key = doc[0].get("Bucket",None) if isinstance(doc[0],dict) else None
            try:
                self._latest_s3_response = self._s3_client.put_object(
                    ACL="bucket-owner-full-control",
                    Body=json.dumps(item),
                    Bucket=bckt_key or self._bucket_name,
                    ContentEncoding="utf-8",
                    Key=doc_key,
                    ServerSideEncryption="AES256",
                    Tagging=f"source={DynamoDbSubtype.TABLE_S3.value}"
                )
            except Exception as e_upload:
                message = f"Layer-DynamoDb-add_one_doc: FAIL to save offloaded document to bucket {self._bucket_name} with key {doc_key}.json. Exception {e_upload}"
                self._logger.error(message)
                raise ConnectionError(message)
            # In the DynamoDb we'll store top-level document properties of base types (to provide search functionality)
            updated_item = {k:v if isinstance(v, (str,int,float,bool)) else "offloaded" for k,v in item.items()}
        else:
            updated_item = item
        
        # Insert record into the table
        try:
            (expression_attribute_names, expression_attribute_values) = self._expr_attr_names_values_for(updated_item)
            self._latest_ddb_response = self._ddb_client.put_item(
                TableName=self._table_name,
                Item=self._primary_key(doc[0]),
                ReturnValues="ALL_NEW",
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
        except Exception as e:
            message = f"Layer-DynamoDb-add_one_doc: FAIL to save document to DynamoDb with exception {e}"
            self._logger.error(message)
            raise ConnectionError(message)

    def doc_by_id(self, *, doc_id:Union[str,Dict[str,any]]) -> dict:
        ''' get document with specified id from the document db. Returns a dictionary.  Index "[]" operator can also be used '''

        # Verify Value in the doc_id
        # If Empty return an empty dictionary
        if doc_id is None:
            self._logger.error(f"Layer-DynamoDb-doc_by_id: no doc_id provided!")
            return {}

        # for table+s3 we need to collect the document from the S3 bucket
        if self.type == DynamoDbSubtype.TABLE_S3:
            doc_key = self._s3_key_for_docid(doc_id)
            bckt_key = doc_id.get("Bucket",None) if isinstance(doc_id,dict) else None
            try:
                self._latest_s3_response = self._s3_client.get_object(
                    Bucket=bckt_key or self._bucket_name,
                    Key=doc_key
                )
                self._logger.debug(f"Layer-DynamoDb-doc_by_id: object collected from the s3 bucket. Will deserialize...")
                s3_deserialized = json.loads(self._latest_s3_response["Body"].read().decode("utf-8"))
                return s3_deserialized
            except Exception as e:
                message = f"Layer-DynamoDb-doc_by_id: FAIL to collect document offloaded to S3 bucket '{self._bucket_name}' under key '{doc_key}' with exception {e}."
                self._logger.error(message)
                raise ConnectionError(message)

        try:
            # collect document from the DynamoDb
            self._latest_ddb_response = self._ddb_client.get_item(
                Table=self._table_name,
                Key=self._primary_key(doc_id),
                # no other parameters required as we retrieving all attributes
            )
        except Exception as e:
            message = f"Layer-DynamoDb-doc_by_id: Fail to get item with exception {e}"
            self._logger.error(message)
            raise ConnectionError(message)

        if (not isinstance(self._latest_ddb_response, dict)) or (not "Item" in self._latest_ddb_response) or (not isinstance(self._latest_ddb_response['Item'], dict)):
            self._logger.warning(f"Layer-DynamoDb-doc_by_id: response empty or not right")
            return {}
        return {
            k:replace_decimals(self._value_from_attr(v)) 
            for k,v in self._latest_ddb_response['Item'].items() if not str(k).startswith("aws:")
        }


    def query_by_value(self, *, 
            doc_values:Dict[str,any], 
            doc_id:Dict[str,any]=None, 
            limit:int=None, start_from:Union[str,Dict[str,any]]=None,
            native_options:any=None
        ) -> list:
        ''' Get documents with same key/values and key part from the dynamo db. Returns a List
            doc_id MUST have key=partition key name and value=desired partition key 
                    this is meaningful ONLY when Table has composite primary key (partition AND sort keys)!
                    sort key conditions ARE NOT SUPPORTED for now. Result is unpredictable if included!
                NOTE: partition/sort keys are used 'as is' and SHOULD NOT be a reserved words!
        '''
        if doc_id is None:
            raise RuntimeError(f"Layer-DynamoDb-query_by_value: query w/o partition key is not supported for now")

        try:
            # Call the Query Method passing in the required parameters
            (expression_attribute_names, expression_attribute_values) = self._expr_attr_names_values_for(doc_values)
            query_params:Dict[str,any] = {
                "TableName": self._table_name,
                "Select": "ALL_ATTRIBUTES",
                # A comparator for evaluating attributes. For example, equals, greater than, less than, etc.
                "ComparisonOperator": "EQ",
                # A string that contains conditions that DynamoDB applies after the Query operation, 
                # but before the data is returned to you. 
                # Items that do not satisfy the FilterExpression criteria are not returned.
                # "FilterExpression": None,

                # The condition that specifies the key values for items to be retrieved by the Query action.
                # The condition must perform an equality test on a single partition key value.
                # If you also want to provide a condition for the sort key, it must be combined using AND with the condition for the sort key. 
                # For example: 'partitionKeyName = :partitionkeyval AND sortKeyName = :sortkeyval'
                "KeyConditionExpression": " AND ".join([f"{k} = {v}" for k,v in doc_id.items()]),

                "ExpressionAttributeNames": expression_attribute_names,
                "ExpressionAttributeValues": expression_attribute_values
            }
            if start_from:
                query_params["ExclusiveStartKey"] = self._primary_key(start_from)
            # Invoke command
            try:
                self._latest_ddb_response = self._ddb_client.query(
                    **query_params,
                    **native_options
                )
            except Exception as req_e:
                message = f"Layer-DynamoDb-query_by_value: Fail to get item with exception {req_e}"
                self._logger.error(message)
                raise ConnectionError(message)
            # Set return value equal to the List
            items = [
                {k:replace_decimals(self._value_from_attr(v)) for k,v in each_item.items()}
                for each_item in self._latest_ddb_response['Items'] if isinstance(each_item, dict)
            ]
            return items
        except Exception as e:
            self._logger.error(f"Layer-DynamoDb-query_by_value: Fail to query with exception {e}")
            # Create an Empty List and Return
            return []

    def scan_and_filter(self, *, 
            doc_values:Dict[str,any], 
            doc_id:Dict[str,any], 
            limit:int=None, start_from:Union[str,Dict[str,any]]=None,
            native_options:any=None
        ) -> list:
        ''' Get documents with same key/values from the document db using ineffective scan. Returns a List '''
        raise RuntimeError(f"Layer-DynamoDb-scan_and_filter: Not supported for now")

        #     # Set variables used to build filterexpression
        #     count1 = 0
        #     filterexpression = ""

        #     # If dictionary is empty return [] list
        #     if len(doc_values) > 0:
        #         # Loop Thru Dictionary and Build the String
        #         try:
        #             self._logger.debug(f"Layer-DynamoDb-query_by_value: create filter from doc_values dict {json.dumps(doc_values)}")
        #         except:
        #             self._logger.warning(f"Layer-DynamoDb-query_by_value: will try to create filter from NONSERIALIZIBLE doc_values dict")

        #         for k, v in doc_values.items():
        #             filterexpression = filterexpression + "Key('" + str(k) + "').eq(" 
        #             # Check what type value is to know what to do with it.
        #             if type(v) is str:
        #                 filterexpression = filterexpression + "'" + str(v) + "'" + ")"
        #             else:
        #                 filterexpression = filterexpression + str(v) + ")"

        #             count1 = count1 + 1
        #             if ((count1 < len(doc_values)) & (count1 != len(doc_values))):
        #                 filterexpression = filterexpression + " & "

        #         # Add in Exception Handling (make sure this is necessary)
        #         try:
        #             # Call the Scan Method passing in the Filter Expression
        #             response = self._table.scan(
        #                 FilterExpression=eval(filterexpression)
        #             )

        #             result = []
        #             for each_item in response['Items']:
        #                 if isinstance(each_item, dict):
        #                     result.append({k:replace_decimals(v) for k,v in each_item.items()})
        #         except Exception as e:
        #             self._logger.error(f"Layer-DynamoDb-query_by_value: Fail to execute scan on table")
        #             self._logger.error(e)
        #             # Create an Empty List and Return
        #             return []
        #     else:
        #         try:
        #             # Call the Scan Method passing in the Filter Expression
        #             response = self._table.scan()
        #             result = []
        #             for each_item in response['Items']:
        #                 if isinstance(each_item, dict):
        #                     result.append({k:replace_decimals(v) for k,v in each_item.items()})
        #         except Exception as e:
        #             self._logger.error(f"Layer-DynamoDb-query_by_value: Fail to scan all records from table")
        #             self._logger.error(e)
        #             # Create an Empty List and Return
        #             return []
        #         # Create an Empty List and Return
        #         #return []
            
        #     # Initialize counter for determining number of pages
        #     scanCNT= 1
        #     if "LastEvaluatedKey" in response:
        #         self._logger.debug(f"Layer-DynamoDb-query_by_value: will aggregate paginated DynamoDb response.")
        #         # Limit to the 30 pages - pass back data once > 30 but log more than 30 available
        #         try:
        #             while 'LastEvaluatedKey' in response: 
        #                 response = self._table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        #                 result.extend(response['Items'])
        #                 if (scanCNT > self._MAX_NUMBER_OF_RESPONSE_PAGES_ASSEMBLED):
        #                     self._logger.error(
        #                     "More than 30 Response Pages were assembled")
        #                     break
        #                 # Increment Counter
        #                 scanCNT = scanCNT + 1
        #         except Exception as e:
        #             self._logger.error(f"Layer-DynamoDb-query_by_value: Fail to aggregate multipage response")
        #             self._logger.debug(e)
        #             raise e
        #     # Set return value equal to the List
        #     res_list = []
        #     for one_rec in result:
        #         # filter out AWS specific records (key of format "aws:*") - they are NOT SERIALIZABLE
        #         upd_rec = {k:replace_decimals(v) for k,v in one_rec.items() if not str(k).startswith("aws:")}
        #         res_list.append((upd_rec[self._primary_key], upd_rec))

        #     try:
        #         self._logger.debug(f"Layer-DynamoDb-query_by_value: number of records {len(result)} in result {result}")
        #         self._logger.debug(f"Layer-DynamoDb-query_by_value: number of records {len(res_list)} in res_list {res_list}")
        #         self._logger.debug(f"Layer-DynamoDb-query_by_value: serialized\nresult: {json.dumps(result)}\nres_list:{json.dumps(res_list)}")
        #     except:
        #         self._logger.debug(f"Layer-DynamoDb-query_by_value: fail to serialize result data")
            
        #     return res_list
  

    def delete_one_doc(self, *, doc_id:Union[str,Dict[str,any]]):
        ''' delete one document from the NoSqlDatasource NOTE: existing document will be removed!'''
        # Verify Value in the doc_id
        if doc_id:
            try:
                self._latest_ddb_response = self._ddb_client.delete_item(
                    Table=self._table_name,
                    Key=self._primary_key(doc_id)
                )
            except Exception as req_e:
                message = f"Layer-DynamoDb-delete_one_doc: Fail to delete item with exception {req_e}"
                self._logger.error(message)
                raise ConnectionError(message)

            # fow table+s3 we need to delete the document from the S3 bucket also
            if self.type == DynamoDbSubtype.TABLE_S3:
                doc_key = self._s3_key_for_docid(doc_id)
                try:
                    self._latest_s3_response = self._s3_client.delete_object(
                        Bucket=self._bucket_name,
                        Key=doc_key
                    )
                    return
                except Exception as e:
                    message = f"Layer-DynamoDb-doc_by_id: FAIL to delete document offloaded to S3 bucket '{self._bucket_name}' under key '{doc_key}' with exception {e}."
                    self._logger.error(message)
                    raise ConnectionError(message)
            return 
        else:
            return

    def update_one_doc_properties(self, *, doc_id:Union[str,Dict[str,any]], props:dict):
        ''' update one document with properties and values from dictionary passed in ''' 
        raise RuntimeError(f"Layer-DynamoDb-update_one_doc_properties: Not supported for now")

        # # Verify that the incoming dictionary has values to process (required)
        # if not isinstance(props, dict):
        #     message = f"Layer-DynamoDb-update_one_doc_properties: provided properties are not right {props}. Must be non-empty dict!"
        #     self._logger.warning(message)
        #     return

        # if self.type == DynamoDbSubtype.TABLE_S3:
        #     # CATE-554 fow table+s3 we need to update the document in the S3 bucket also
        #     # as we have to update both DynamoDb AND file in the S3 bucket
        #     # the easiest way will be to retrieve the document and then save it
        #     current_doc = self.doc_by_id(doc_id=doc_id)
        #     # update properties
        #     for k,v in props.items():
        #         current_doc[k] = v
        #     # now save the doc
        #     self.add_one_doc(doc=(doc_id, current_doc))
        #     return

        # # For the clean DynamoDb implementation (w/o S3 bucket) we can use DynamoDb update_item method
        # # Build the Update Expression, Expression Attribute Values and Names for input to the table update
        # update_expression = 'SET {}'.format(','.join(f'#{k}=:{k}' for k in props))
        # expression_attribute_values = {f':{k}': v for k, v in props.items()}
        # expression_attribute_names = {f'#{k}': k for k in props}

        # # Add in Exception Handling (make sure this is necessary)
        # try:
        #     # Call the Table Update Method passing in the Update Expression, Expression Attribute Values and Names
        #     response = self._table.update_item(
        #         Key={
        #             self._primary_key : doc_id,
        #         },
        #         UpdateExpression=update_expression,
        #         ExpressionAttributeValues=expression_attribute_values,
        #         ExpressionAttributeNames=expression_attribute_names,
        #         ReturnValues='UPDATED_NEW',
        #     )
        #     return
        # except Exception as e:
        #     self._logger(f"Layer-DynamoDb-update_one_doc_properties: FAIL to update properties for the document {doc_id} with exception {e}")
        #     return

    
    # need eventually
    def serialize(self) -> dict:
        ''' Returns the whole Doc Db as one dict '''
        # must convert a tuple to a dict  
        # this method will call the query by value method but not passing in any parameters or values could be empty?
        self._logger.debug(f"Layer-DynamoDb-serialize: will collect all records from DynamoDb using scan with empty filter")
        lst = self.query_by_value(doc_values = {})
        res_dct = {v[0]: v[1] for v in lst}
        return res_dct

    # need eventually
    def deserialize(self, source: dict):
        ''' Inject Doc Db from dict format '''
        pass

    # implementation not required for DynamoDB
    def _save(self, option="json"):
        ''' save the Doc Db in the local files system in specific format (tsv, json) '''
        pass

    # implementation not required for DynamoDB
    def _load(self, option="json"):
        ''' load the Doc Db from the local files system in specific format (tsv, json) '''
        pass

    # implementation not required for DynamoDB
    def _clean(self):
        #self._file_name = DynamoDb._DEFAULT_TABLE_NAME
        pass
    
    # future implementation
    def _convert_strings(self, props:dict) -> dict:
        # if the value is a container (list, dict, tuple, set) than serialize to a json string
        # Convert values into Props:dict if they are not strings
        # When implementing this feature will need to serialize in and deserialize out
        return {k:json.dumps(v) if isinstance(v, (tuple, list, set, dict)) else v for k,v in props.items()}
