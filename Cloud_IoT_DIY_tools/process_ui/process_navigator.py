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

import logging
_top_logger = logging.getLogger(__name__)

#--- Proprietary modules
from cloud_client import AwsCloudClient, CloudClient
from thingcomm_client import ThingCommClient
from process_ui.data_model import StepState, DataModel, CommandToExecute


#####################################################################
class ProcessNavigator(ABC):

    def __init__(self, data:DataModel=None, navigator_id:str=None, parent_navigator:ProcessNavigator=None) -> None:
    # def __init__(self, cloud_client:CloudClient, navigator_id:str=None, parent_navigator:ProcessNavigator=None) -> None:
        self.navigator_id = navigator_id
        # self._cloud_client = cloud_client
        self.steps:Dict[str, StepController] = None
        self._delegates:Dict[str, Callable] = None
        self._parent:ProcessNavigator = parent_navigator
        # self.data - backend
        self._data:DataModel = data or parent_navigator.data if parent_navigator else None
        #--------- Project config file location
        self.config_file_location = None
        #--------- Project .gitignore location
        self.gitignore_location = None
        #--------- Refresh main window callback
        # self.refresh_main_window_callback:Callable = None
        self.current_window:sg.Window = None
        #-----------------------------------------
        # Command execution in service window
        self._service_window:sg.Window = None
        self.command:CommandToExecute = None
        self.command_process:subprocess.Popen = None
        self.command_thread:threading.Thread = None
        self.command_output_queue:Queue = None
        self.process_output:List[str] = None
        self.command_errors_thread:threading.Thread = None
        self.command_errors_queue:Queue = None
        self.process_errors:List[str] = None
        #-----------------------------------------
        # Logs for multi-step execution outside of service window
        self.background_process_completion_queue:Queue = None
        self.background_process_message:str = None
        self.logs_element_name:str = None


    ########################################################################################
    # Data Model Methods
    @property
    def data(self)->DataModel:
        ''' this method will propagate the Data Model reference to child Navigators '''
        if self._data is None:
            if self._parent and self._parent._data:
                self._data = self._parent._data
        return self._data
    @data.setter
    def data(self, value:DataModel):
        if not isinstance(value, DataModel):
            raise ValueError("An attempt to assign incorrect Data Model")
        self._data = value
    
    ########################################################################################
    # Thing Comm Methods
    #
    @property
    def thingcomm_client(self) -> ThingCommClient:
        return self.data.instance_config["thingcomm_client"]
    @thingcomm_client.setter
    def thingcomm_client(self, value:ThingCommClient):
        self.data.instance_config["thingcomm_client"] = value

    ########################################################################################
    # Cloud Methods
    #
    @property
    def cloud_client(self) -> CloudClient:
        return self.data.instance_config["cloud_client"] #self._cloud_client
    @cloud_client.setter
    def cloud_client(self, value:CloudClient):
        ''' recursively update '''
        self.data.instance_config["cloud_client"] = value

    ########################################################################################
    # Process StepControllers and Model methods
    #
    def root(self)->ProcessNavigator:
        ''' '''
        if self._parent:
            return self._parent.root()
        return self

    def activate_next(self)->StepController:
        self.current_step()._state = StepState.COMPLETED
        next_vc = self.next_step()
        if next_vc is None:
            if self._parent:
                return self._parent.activate_next()
        else:
            next_vc._active = True
            next_vc._state = StepState.CONFIGURATION
            return True
        return False

    def current_step(self) -> StepController:
        ''' returns latest active step '''
        res = None
        for v in self.steps.values():
            if v.is_active:
                res = v
                continue
            else:
                return res
        return res

    def next_step(self) -> StepController:
        ''' returns next step after last active '''
        prev:bool = True
        for v in self.steps.values():
            if v.is_active:
                prev = v.is_active
                continue
            else:
                return v
        return None

    ########################################################################################
    # Model visualization
    #
    def tab_group(self) -> sg.TabGroup:
        tabs = {
            k:step_vc._updtab() if step_vc.is_active else sg.Tab(step_vc.step_id,[[sg.Text("Disabled")]],disabled=True) 
                for k,step_vc in self.steps.items()
        }
        tgroup = sg.TabGroup( 
            [  list(tabs.values()) ], 
            enable_events=True,
            key=self.navigator_id
        )
        return tgroup

    ########################################################################################
    # Model delegates
    #
    def delegates(self) -> Dict[str, Callable]:
        ''' aggregate all delegates from underlying steps with control over duplicates '''
        # if self._delegates is None:
        res = {}
        for step_vc in self.steps.values():
            for event_name, event_handler in step_vc.delegates().items():
                if event_name in res:
                    raise ValueError(f"Duplicating event name {event_name} in Step Controller {step_vc.step_id}")
                res[event_name] = event_handler
        self._delegates = res
        return self._delegates

    ########################################################################################
    # Command execution in service window
    #
    def execute_command(self, command:CommandToExecute, timeout=10.0):
        ''' ASYNC command execution. 
            Command will be executed in the subprocess.
            Subprocess output will be handled by Thread
            Output to be placed to self.command_output_queue by Thread
            Main UI Loop will read the queue and update results
        '''
        def enqueue_subprocess_output(out, queue):
            for line in iter(out.readline, b''):
                queue.put(line)
            out.close()

        def enqueue_subprocess_error(out, queue):
            for line in iter(out.readline, b''):
                queue.put(line)
            out.close()

        cmd = command.cmd
        self.process_output = []
        self.process_errors = []
        self.command_output_queue = Queue()
        self.command_errors_queue = Queue()
        popen_params = {
            "args": cmd, 
            "stdout": subprocess.PIPE, 
            "stderr": subprocess.PIPE, 
            "close_fds": ON_POSIX, 
            "shell": True
        }
        if command.cwd:
            popen_params["cwd"] = command.cwd
        self.command_process = subprocess.Popen(**popen_params)
        # Create Thread to forward STDOUT to queue
        self.command_thread = threading.Thread(
            target=enqueue_subprocess_output, 
            args=(self.command_process.stdout, self.command_output_queue)
        )
        # Create Thread to forward STDERR to queue
        self.command_errors_thread = threading.Thread(
            target=enqueue_subprocess_error, 
            args=(self.command_process.stderr, self.command_errors_queue),
        )
        self.command_thread.start()
        self.command_errors_thread.start()

    def cancel_command(self):
        ''' '''
        if self.command_process:
            try:
                self.command_process.terminate()
                self.command_process.kill()
                os.killpg(os.getpgid(self.command_process.pid), signal.SIGTERM)
                self.command_process = None
            except ProcessLookupError:
                self.command_process = None
            except Exception as e:
                _top_logger.warning(f"Fail to kill process with exception {e}")
                pass
            

    ########################################################################################
    # Service window for executed commands output
    #
    @property
    def stdout_key(self)->str:
        return "Command STDOUT"
    @property
    def stderr_key(self)->str:
        return "Command STDERR"
    @property
    def command_cancel_key(self)->str:
        return "Terminate operation subprocess"
    @property
    def command_success_key(self)->str:
        return "Close service window on FAIL"
    @property
    def command_failure_key(self)->str:
        return "Close service window on SUCCESS"

    def service_window(self)->sg.Window:
        ''' '''
        if self._service_window is None:
            layout = [
                [
                    sg.Multiline(size=(120,50), background_color="black", text_color="yellow", key=self.stdout_key, expand_x=True, expand_y=True),
                    # If cannot catch STDERR Output can be used instead
                    # sg.Output(size=(70,50), background_color="black", text_color="orange", key=self.stderr_key, expand_x=True, expand_y=True)
                    sg.Multiline(size=(70,50), background_color="black", text_color="orange", key=self.stderr_key, expand_x=True, expand_y=True)
                ],
                [
                    sg.Button("Cancel operation", key=self.command_cancel_key, enable_events=True), 
                    sg.Button("Failed", key=self.command_failure_key, enable_events=True, disabled=True),
                    sg.Button("Success", key=self.command_success_key, enable_events=True, disabled=True)
                ]
            ]
            self._service_window:sg.Window = sg.Window(
                'Operations Window', layout, 
                background_color="black", 
                # disable_close=True, disable_minimize=True,
                finalize=True)
        return self._service_window
    
    def close_service_window(self):
        ''' '''
        if self._service_window:
            if self.command_process:
                self.cancel_command()
            self._service_window.close()
            self._service_window = None
    ########################################################################################



#####################################################################
class StepController(ABC):
    
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        ''' '''
        self._navigator = navigator
        self._step_id:str = None
        self._active:bool = False
        self._state:StepState = StepState.DISABLED
        self._update_view:bool = False
        self._exec_results:str = None
        self._tab:sg.Tab = None
        self._tab_group:sg.TabGroup = None
        self._subnavigator:ProcessNavigator = None
        self.uuid = uuid4()


    @property
    def step_id(self)->str:
        return self._step_id

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def state(self) -> StepState:
        return self._state

    @property
    def cloud(self) -> CloudClient:
        return self._navigator.cloud_client

    def _updtab(self):
        ''' this is actually a decorator for StepController Tab calls from Model '''
        if self.state==StepState.COMPLETED:
            ttab = sg.Tab(
                self._step_id, 
                [[ sg.Text(f"All steps were completed! You can close the window now.", font="Arial 15 bold") ]],
                disabled=not (self._navigator.root().current_step().state==StepState.COMPLETED and self._navigator.root().next_step() is None)
            )            
        else:
            ttab = self.tab()
            # if self.is_active:
            #     ttab.Select()
        ttab.k = f"tab|{self.step_id}|{uuid4()}"
        return ttab

    def tab(self)->sg.Tab:
        ''' each tab defines sub-step UNLESS step has it's own model!'''
        if isinstance(self._subnavigator, ProcessNavigator):
            return sg.Tab(
                    self.step_id,
                    [[ self._subnavigator.tab_group() ]],
                    disabled=not self.is_active,
                    # key=f"tab|{self.step_id}",
                    # tooltip=None if step_vc.is_active else "This step not allowed yet"
                )
        else:
            raise ValueError(f"{self.step_id} MUST have tabs method defined!")

    def next_step(self, event_values)->ProcessNavigator:
        self._state = StepState.COMPLETED
        next_vc = self._navigator.activate_next()
        if next_vc is None:
            ''' last step completed '''
            return None
        else:
            return self._navigator.root()


    @abstractmethod
    def delegates(self)->Dict[str, Callable[[Dict], ProcessNavigator]]:
        ''' for each tab we need dict of event handlers '''
