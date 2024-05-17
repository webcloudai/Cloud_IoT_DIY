'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License

NoSqlDatasource implementation with file '''

import logging
from importlib import import_module
from Layer_lib_NoSqlDatasource_providers import ANoSqlDatasource
import json

class FileDb(ANoSqlDatasource):
    ''' Document Db implementation with Tab Separated Value, pickle or JSON File 
        Properties:
        @static _csv, _pickle   - static placeholder for lazily loaded Python csv and pickle modules
        _connection             - dict of connection properties
        _DEFAULT_FILE_NAME      - predefined name of the file (if not provided in connection)
        _docs                   - dict representing in memory document db
    '''
    _csv = None
    _pickle = None

    # backing storage option classifiers
    _STORAGE_LOCAL = "local"
    _STORAGE_AWS = "aws"
    _STORAGE_AZURE = "azure"
    # default db file name
    _DEFAULT_FILE_NAME = "Layer_NoSqlDatasource"

    def __init__(self, connection:dict):
        ''' dynamically load module while connection defines where to save'''
        self._clean()

        if isinstance(connection, dict) and "type" in connection and isinstance(connection["type"], str):
            self._type = connection["type"]
        else:
            self._logger.info("local file system will be used as connection property was not provided or incorrect")
        if self._type == self._STORAGE_LOCAL:
            if isinstance(connection, dict) and "folder" in connection and isinstance(connection["folder"], str):
                self._folder = connection["folder"]
            else:
                self._logger.info("current folder will be used as connection property was not provided or incorrect")
        elif self._type == self._STORAGE_AWS:
            # TO DO item - FileDb on AWS with S3 as storage backend
            self._logger.error(f"Type {self._type} is not supported by FileDb for now")
            raise ValueError
        elif self._type == self._STORAGE_AZURE:
            # TO DO item - FileDb on Azure with Storage Account as storage backend
            self._logger.error(f"Type {self._type} is not supported by FileDb for now")
            raise ValueError
        else:
            self._logger.error(f"Type {self._type} is not supported by FileDb for now")
            raise ValueError

        self._connection = connection
        if "file_name" in connection and isinstance(connection["file_name"], str):
            self._file_name = connection["file_name"]
        else:
            self._logger.info(f"{self._file_name} will be used as connection property was not provided or incorrect")
        # try to load file db
        loaded = False
            # try to load graph
        for opt in ["json", "pickle", "tsv"]:
            try:
                self._load(option=opt)
                loaded = True
                break
            except:
                pass
        if not loaded:
            self._logger.info(f"FileDb with file name {self._file_name} was not able to load")

    @property
    def connection(self):
        return self._connection

    def add_docs(self, *, docs:list):
        ''' in memory implementation. NoSqlDatasource to be saved to store the information! '''
        for one_doc in docs:
            #self._docs[str(one_doc[0])] = one_doc[1]
            self.add_one_doc(doc=one_doc)
        self._save()

    def add_one_doc(self, *, doc:tuple):
        ''' in memory implementation. NoSqlDatasource to be saved to store the information! '''
        self._docs[str(doc[0])] = doc[1].copy()
        self._save()

    def update_one_doc_properties(self, *, doc_id:str, props:dict):
        ''' update one document with properties and values from props ''' 
        for k,v in props.items():
            self._docs[str(doc_id)][k] = v
        self._save()
        return self._docs[str(doc_id)]

    def delete_one_doc(self, *, doc_id:str)->bool:
        ''' delete one document from the NoSqlDatasource. NOTE: existing document will be removed!'''
        try:
            self._docs.pop(doc_id)
            self._save()
            return True
        except:
            # no document to delete
            return False

    def doc_by_id(self, *, doc_id:str)->dict:
        return self._docs[str(doc_id)]

    def query_by_value(self, *, doc_values:dict)->list:
        ''' "AND query"
            return list of documents where required key exists and has correct value
        '''
        result = []
        for doc_id,doc in self._docs.items():
            has_kv = True
            for k,v in doc_values.items():
                if k not in doc or doc[k] != v:
                    has_kv = False
                    break
            if has_kv:
                result.append((doc_id, doc))
        return result

    def query_one_doc_by_value(self, *, doc_id: str, doc_values: dict) -> list:
        ''' Get documents with same key/values and primary key from the document db. Returns a List '''
        return [self.doc_by_id(doc_id=doc_id)]

    def _clean(self):
        self._docs = {}
        self._file_name = FileDb._DEFAULT_FILE_NAME

    def serialize(self)->dict:
        ''' Returns the whole Doc Db as one dict '''
        return self._docs

    def deserialize(self, source:dict):
        ''' Inject Doc Db from dict format '''
        self._docs = {str(k):v for k,v in source.items()}

    def _save(self, option="json"):
        ''' save the Doc Db in the local files system in specific format (tsv, json) '''
        if option == "tsv":
            if len(self._docs) == 0:
                self._logger.warning("Attempt to save empty Db. Nothing to save!")
            if FileDb._csv == None:
                FileDb._csv = import_module("csv")
            # collect all documents keys
            all_keys = {}
            i = 1
            for doc in self._docs.values():
                for k in doc.keys():
                    all_keys.setdefault(k, i)
                    i += 1
            with open(f"{self._file_name}.tsv", mode='w') as tf:
                tsv_writer = FileDb._csv.writer(tf, dialect=FileDb._csv.excel_tab)
                titles=list(all_keys.keys())
                tsv_writer.writerow([self._primary_key]+titles)
                for doc_id,doc in self._docs.items():
                    one_row = [doc_id]
                    for k in titles:
                        if k in doc:
                            if isinstance(doc[k],int) or isinstance(doc[k],float) or isinstance(doc[k],str) or isinstance(doc[k],bool):
                                one_row.append(doc[k])
                            #elif isinstance(doc[k],bool):
                            #    one_row.append('true' if doc[k] else 'false')
                            else:
                                one_row.append(json.dumps(doc[k]))#.replace('"',"'"))
                        else:
                            one_row.append("#-|NA|-#")
                    tsv_writer.writerow(one_row)
        elif option == "json":
            with open(f"{self._file_name}.json", mode='w') as jf:
                json.dump(self._docs,jf)
        elif option == "pickle":
            if FileDb._pickle == None:
                FileDb._pickle = import_module("pickle")
            with open(f"{self._file_name}.pickle", mode='bw') as pf:
                FileDb._pickle.dump(self._docs,pf)
        else:
            self._logger.error(f"{option} is not supported by FileDb")
            raise ValueError

    def _load(self, option="json"):
        ''' load the Doc Db from the local files system in specific format (tsv, json) '''
        if option == "tsv":
            # Tab separated table where first line has field names and first column documents ids
            if FileDb._csv == None:
                FileDb._csv = import_module("csv")
            titles = None
            with open(f"{self._file_name}.tsv", mode='r') as tf:
                lines = FileDb._csv.reader(tf, dialect=FileDb._csv.excel_tab)
                for line in lines:
                    if titles == None:
                        titles = line
                    else:
                        self._docs[str(line[0])] = {}
                        for i,v in enumerate(line):
                            # we'll not add self._primary_key to the dict (if it was not there) and will not add "NA"
                            if i>0 and v != "#-|NA|-#":
                                # we need to cast serialized objects
                                if v == "True":
                                    self._docs[str(line[0])][titles[i]] = True
                                elif v == "False":
                                    self._docs[str(line[0])][titles[i]] = False
                                else:
                                    try:
                                        self._docs[str(line[0])][titles[i]] = json.loads(v)
                                    except:
                                        self._docs[str(line[0])][titles[i]] = v
        elif option == "json":
            with open(f"{self._file_name}.json", mode='r') as jf:
                self._docs = json.load(jf)
        elif option == "pickle":
            if FileDb._pickle == None:
                FileDb._pickle = import_module("pickle")
            with open(f"{self._file_name}.pickle", mode='br') as pf:
                self._docs = FileDb._pickle.load(pf)
        else:
            self._logger.error(f"{option} is not supported by FileDb")
            raise ValueError
