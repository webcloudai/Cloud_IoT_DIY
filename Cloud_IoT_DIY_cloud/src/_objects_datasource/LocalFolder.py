'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License

ANoSqlDatasource implementation with file '''
#! NOTE that LocalFolder depends on aiofiles for effective multi-files handling!

from dataclasses import dataclass
from pathlib import Path
from typing import Union, Dict, List, ByteString
import json
import asyncio
from importlib import import_module

import logging
_top_logger = logging.getLogger(__name__)
from . import ObjectsDatasource

async def read_the_file(file_path:Path, encoding:str=None, format:str=None)->Union[ByteString, str, Dict, List]:
    ''' async non-blocking file read '''
    try:
        if encoding is None:
            ''' just read file as binary '''
            async with LocalFolder._aiofiles.open(file_path, mode="rb") as handle:
                # read the contents of the file
                data = await handle.read()
            return data
        else:
            async with LocalFolder._aiofiles.open(file_path, mode="r", encoding=encoding) as handle:
                # read the contents of the file with encoding
                data = await handle.read()
            if format is None:
                return data
            else:
                ''' json load '''
                return json.loads(data)
    except Exception as e:
        _top_logger.warning(f"Fail to read {file_path} with exception {e}")
    return None

@dataclass(eq=True, frozen=True)
class LocalFolderConfig:
    folder_path:Path        # - the path to the local folder serving as Datasource

class LocalFolder(ObjectsDatasource):
    ''' 
        ObjectsDatasource implementation with local folders
    '''
    _aiofiles_module = None    # we'll load this modules dynamically if/when needed

    @staticmethod
    def _aiofiles(self):
        if LocalFolder._aiofiles_module is None:
            LocalFolder._aiofiles_module = import_module("aiofiles")
        return LocalFolder._aiofiles_module

    def __init__(self, config:dict):
        '''  '''
        # Verify that the config contains a dictionary object with required parameters
        try:
            self._config = LocalFolderConfig(**config)
        except Exception as e:
            self._logger.error("Layer-LocalFolder: config should be a dict and has required values. Failed with exception {e}")
            raise ValueError

        self._path:Path = Path(self._config.folder_path)

    def list_objects(self, prefix:str=None, filter:str=None)->List[str]:
        ''' list all objects in the Datasource '''
        if isinstance(filter, str):
            glob_filter = f"**/{filter}"
        elif isinstance(prefix, str):
            glob_filter = f"**/{prefix}*"
        else:
            glob_filter = "**/*"
        result = [str(v).replace(f"{str(self._path)}","") for v in self._path.glob(glob_filter) if v.is_file()]
        return [v[1:] if v.startswith("/") else v for v in result]

    def get_blob(self, key:str)->ByteString:
        ''' get the blob from the Datasource '''
        file_path = self._path / Path(key)
        result = None
        try:
            with open(file_path, "rb") as f:
                result = f.read()
        except Exception as e:
            _top_logger.error(f"Fail to collect blob with exception {e}")
            raise e
        return result

    async def get_objects(self, filter:str, keys:List[str], encoding:str="utf8", format:str="json")->List[Union[ByteString, str, Dict, List]]:
        ''' get all objects from the Datasource '''
        obj_load_tasks = [
            # asyncio.create_task(read_the_file(self._path / Path(v), encoding, format)) 
            read_the_file(self._path / Path(v), encoding, format)
            for v in (keys if isinstance(keys, list) else self.list_objects(filter))
        ]
        results = await asyncio.gather(*obj_load_tasks)
        return results

    def put_object(self, key:str, obj:Union[str, ByteString], encoding:str="utf-8")->bool:
        ''' add the object to the Datasource (replace if exists) '''
        file_path = self._path / Path(key)
        file_subfolders = file_path.parent
        file_subfolders.mkdir(parents=True, exist_ok=True)
        try:
            with open(file_path, f"w{'b' if isinstance(obj, ByteString) else ''}") as f:
                f.write(obj)
        except Exception as e:
            _top_logger.error(f"Fail to write object with exception {e}")
            return False
        return True

    def remove_object(self, key:str)->bool:
        ''' remove (delete) the object from the Datasource '''
        file_path = self._path / Path(key)
        file_subfolders = file_path.parent
        try:
            file_path.unlink()
        except Exception as e:
            _top_logger.error(f"Fail to remove object {key} with exception {e}")
            return False
        # we'll try to remove empty parent folder if any
        while file_path.parent:
            file_path = file_path.parent
            try:
                file_path.rmdir()
            except Exception as e:
                _top_logger.debug(f"Was not able to remove folder {file_path} with exception {e}")
                break
        return True


    def remove_objects(self, filter:str)->List[bool]:
        ''' remove/delete multiple objects from the Datasource '''
        raise RuntimeError("NOT IMPLEMENTED")

    def query_objects(self, meta_data_query:dict)->List[str]:
        ''' query objects by metadata in the Datasource '''
        raise RuntimeError("NOT IMPLEMENTED")
