'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License

ANoSqlDatasource implementation with file '''

from typing import Union, Dict, List, ByteString
from importlib import import_module
from dataclasses import dataclass
from pathlib import Path
import json
import logging
_top_logger = logging.getLogger(__name__)

from . import ObjectsDatasource

@dataclass(eq=True, frozen=True)
class S3BucketConfig:
    bucket_name:str
    key_prefix:str        # - the "path" to the S3 "folder" serving as Datasource


class S3Bucket(ObjectsDatasource):
    ''' 
        ObjectsDatasource implementation with local folders
    '''
    # SOME CONSTANTS
    DELIMITER = "/"

    # dynamically loaded boto3 module
    _boto3 = None

    # Basic client
    _s3_client = None  # NOTE that boto3 clients are thread-safe


    def __init__(self, config:dict):
        '''  '''
        # Verify that the config contains a dictionary object with required parameters
        try:
            self._config = S3BucketConfig(**config)
        except Exception as e:
            _top_logger.error("Layer-LocalFolder: config should be a dict and has required values. Failed with exception {e}")
            raise ValueError
        try:
            self._boto3 = import_module("boto3")
            self._s3_client = self._boto3.client("s3") # NOTE that boto3 clients are thread-safe
        except Exception as e:
            _top_logger.error(f"FAIL to init S3Bucket datasource with exception {e}")
            raise e
        self._prefix:str = self._config.key_prefix
        self._bckt:str = self._config.bucket_name


    def list_objects(self, prefix:str=None, filter:str=None)->List[str]:
        ''' list all objects in the Datasource 
            NOTE that filter is NOT SUPPORTED for now
        '''
        results = []
        continuation_token = True
        obj_prefix = f"{self._prefix}/{prefix}" if isinstance(prefix, str) else self._prefix
        while not continuation_token is None:
            try:
                cl_params = {
                    "Bucket": self._bckt,
                    "Prefix": obj_prefix,
                    "FetchOwner": False,
                    # *NOTE* Multiple AWS SDK defaults are in use !
                    # "Delimiter": self.DELIMITER,  # this one really confusing - should not be used
                    # EncodingType='url',
                    # MaxKeys=123,  # default is 1000
                    # StartAfter='string',
                    # RequestPayer='requester',
                    # ExpectedBucketOwner='string'
                }
                if continuation_token not in [True, None]:
                    cl_params["ContinuationToken"] = continuation_token,
                resp = self._s3_client.list_objects_v2(**cl_params)
                continuation_token = resp.get("NextContinuationToken", None) if resp["IsTruncated"] else None
                results.extend(resp.get("Contents",[]))
            except Exception as e:
                _top_logger.error(f"FAIL to collect objects list from bucket {self._bckt} with prefix {self._prefix} and filter {filter} with exception {e}")
                continuation_token = None

        # for collected results we need to EXCLUDE prefix (if any) and DELIMITER (as it's a DataSource property)
        result = [
            v["Key"][len(self._prefix)+len(self.DELIMITER):] 
                if len(self._prefix)>0 and v["Key"].startswith(self._prefix) else v["Key"]
                    for v in results
        ]
        return result

    def get_blob(self, key:str)->ByteString:
        ''' get the blob from the Datasource '''
        result = None
        try:
            result = self._s3_client.get_object(
                Bucket=self._bckt,
                Key=f"{self._prefix}{self.DELIMITER if len(self._prefix)>0 else ''}{key}",
                # *NOTE* Multiple AWS SDK defaults are in use !
                # IfMatch='string',
                # IfModifiedSince=datetime(2015, 1, 1),
                # IfNoneMatch='string',
                # IfUnmodifiedSince=datetime(2015, 1, 1),
                # Range='string',
                # ResponseCacheControl='string',
                # ResponseContentDisposition='string',
                # ResponseContentEncoding='string',
                # ResponseContentLanguage='string',
                # ResponseContentType='string',
                # ResponseExpires=datetime(2015, 1, 1),
                # VersionId='string',
                # SSECustomerAlgorithm='string',
                # SSECustomerKey='string',
                # RequestPayer='requester',
                # PartNumber=123,
                # ExpectedBucketOwner='string',
                # ChecksumMode='ENABLED'
            )["Body"].read()
        except Exception as e:
            _top_logger.error(f"FAIL to collect blob {key} from bucket {self._bckt} with prefix {self._prefix} with exception {e}")
            result = None
        return result

    async def get_objects(self, filter:str, keys:List[str], encoding:str="utf8", format:str="json")->List[Union[ByteString, str, Dict, List]]:
        ''' get all objects from the Datasource 
        NOTE that S3Bucket get objects is NOT really ASYNC for now!
        '''
        results = []
        for v in (keys if isinstance(keys, list) else self.list_objects(filter)):
            try:
                res = self.get_blob(v)
                if isinstance(encoding, str):
                    res = res.decode(encoding)
                    match format:
                        case "json":
                            res = json.loads(res)
                results.append(res)
            except Exception as e:
                _top_logger.error(f"FAIL to get object {v} with exception {e}")
                continue
        return results

    def put_object(self, key:str, obj:Union[str, ByteString], encoding:str="utf-8")->bool:
        ''' add the object to the Datasource (replace if exists) '''
        try:
            resp =  self._s3_client.put_object(
                Body=obj if isinstance(obj, ByteString) else obj.encode(encoding=encoding),
                Bucket=self._bckt,
                Key=f"{self._prefix}{self.DELIMITER if len(self._prefix)>0 else ''}{key}",
                ServerSideEncryption="AES256",       # 'AES256'|'aws:kms',
                # *NOTE* Multiple AWS SDK defaults are in use !
                # ACL='private'|'public-read'|'public-read-write'|'authenticated-read'|'aws-exec-read'|'bucket-owner-read'|'bucket-owner-full-control',
                # CacheControl='string',
                # ContentDisposition='string',
                # ContentEncoding='string',
                # ContentLanguage='string',
                # ContentLength=123,
                # ContentMD5='string',
                # ContentType='string',
                # ChecksumAlgorithm='CRC32'|'CRC32C'|'SHA1'|'SHA256',
                # ChecksumCRC32='string',
                # ChecksumCRC32C='string',
                # ChecksumSHA1='string',
                # ChecksumSHA256='string',
                # Expires=datetime(2015, 1, 1),
                # GrantFullControl='string',
                # GrantRead='string',
                # GrantReadACP='string',
                # GrantWriteACP='string',
                # Metadata={ 'string': 'string' },
                # StorageClass='STANDARD'|'REDUCED_REDUNDANCY'|'STANDARD_IA'|'ONEZONE_IA'|'INTELLIGENT_TIERING'|'GLACIER'|'DEEP_ARCHIVE'|'OUTPOSTS'|'GLACIER_IR'|'SNOW',
                # WebsiteRedirectLocation='string',
                # SSECustomerAlgorithm='string',
                # SSECustomerKey='string',
                # SSEKMSKeyId='string',
                # SSEKMSEncryptionContext='string',
                # BucketKeyEnabled=True|False,
                # RequestPayer='requester',
                # Tagging='string',
                # ObjectLockMode='GOVERNANCE'|'COMPLIANCE',
                # ObjectLockRetainUntilDate=datetime(2015, 1, 1),
                # ObjectLockLegalHoldStatus='ON'|'OFF',
                # ExpectedBucketOwner='string'
            )
        except Exception as e:
            _top_logger.error(f"FAIL to put object {key} to bucket {self._bckt} with prefix {self._prefix} with exception {e}")
            return False
        return True

    def remove_object(self, key:str)->bool:
        ''' remove (delete) the object from the Datasource '''
        try:
            resp =  self._s3_client.delete_object(
                Bucket=self._bckt,
                Key=f"{self._prefix}{self.DELIMITER if len(self._prefix)>0 else ''}{key}",
                # *NOTE* Multiple AWS SDK defaults are in use !
                # MFA='string',
                # VersionId='string',
                # RequestPayer='requester',
                # BypassGovernanceRetention=True|False,
                # ExpectedBucketOwner='string'
            )
        except Exception as e:
            _top_logger.error(f"FAIL to remove object {key} from bucket {self._bckt} with prefix {self._prefix} with exception {e}")
            return False
        return True


    def remove_objects(self, filter:str)->List[bool]:
        ''' remove/delete multiple objects from the Datasource '''
        raise RuntimeError("NOT IMPLEMENTED")

    def query_objects(self, meta_data_query:dict)->List[str]:
        ''' query objects by metadata in the Datasource '''
        raise RuntimeError("NOT IMPLEMENTED")
