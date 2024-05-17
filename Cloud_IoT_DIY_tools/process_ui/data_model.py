'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable, Union
import PySimpleGUI as sg
from abc import ABC, abstractmethod, abstractproperty
from enum import Enum
from uuid import uuid4

import subprocess
import threading
import sys
import os
import signal
from queue import Queue, Empty
ON_POSIX = 'posix' in sys.builtin_module_names

from pathlib import Path

#--- we'll add path to PATH to enable import of common_project_config
sys.path.append("../Cloud_IoT_DIY_cloud")
from common_project_config import ProjectConfig

import logging
_top_logger = logging.getLogger(__name__)

#--- Proprietary modules
from cloud_client import AwsCloudClient, CloudClient

''' '''
class StepState(Enum):
    DISABLED = "Disabled"
    CONFIGURATION = "Configuration"
    EXECUTION = "Execution"
    EXECUTIONFAILED = "ExecutionFailed"
    EXECUTIONSUCCES = "ExecutionSuccess"
    COMPLETED = "Completed"

#####################################################################
class DataModel(ABC):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.instance_config:Dict[str, any] = kwargs
        self.data = None
        self._project_config:ProjectConfig = None

    def assemble_project_config(self)->ProjectConfig:
        try:
            self._project_config = ProjectConfig.create_from_file()
        except Exception as e:
            _top_logger.error(f"Fail to assemble project config from file")
        return self.project_config
    @property
    def project_config(self)->ProjectConfig:
        return self._project_config

    #====== ABSTRACT PART ======
    @abstractmethod
    def config_data(self)->Dict:
        ''' '''

    @abstractmethod
    def to_dict(self)->Dict:
        ''' '''
    @abstractmethod
    def load_config_from(self, config_location:Path)->Dict:
        ''' '''

    @abstractmethod
    def load_model_data(self):
        raise ValueError("TO BE IMPLEMENTED IN CHILD")

    @abstractmethod
    def save_model_data(self):
        raise ValueError("TO BE IMPLEMENTED IN CHILD")

    @abstractmethod
    def update_by_parameter_route(self, route:List[str], value:any):
        ''' '''
    
    @abstractmethod
    def update_local_file(self, **kwargs):
        ''' '''
#####################################################################
class CommandToExecute:
    def __init__(self, cmd_with_args:Union[str, List[str]], delegate:Callable, **kwargs) -> None:
        self.cmd:List[str] = cmd_with_args# if isinstance(cmd_with_args, list) else cmd_with_args.split(" ")
        self.delegate:Callable = delegate
        self.cwd:Path = kwargs.get("cwd",None)

