'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, Tuple, Callable
import PySimpleGUI as sg
from pathlib import Path
import json
import logging
_top_logger = logging.getLogger(__name__)

#--- Proprietary modules
from thingcomm_client import ThingCommClient, ThingCommFactory, ThingCommType
from cloud_client import AwsCloudClient, CloudClient
from process_ui.data_model import StepState, DataModel, CommandToExecute
from process_ui.process_navigator import ProcessNavigator, StepController
from thing_prov.steps import Step



#####################################################################
# Step 4. Update firmware and UI with cloud-specific parameters
class CommSetupStepController(StepController):
    TEMP_IP_SCAN_FILE = "_ip_addresses_found.json"
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.CommSetup.value
        self.model_data:DataModel = self._navigator.data
        self.project_config = self.model_data.project_config or self.model_data.assemble_project_config()
        self._active:bool = True     # first step is always active
        self.networkscan_command = f"python scan_ip.py -o {self.TEMP_IP_SCAN_FILE} -t 80"
        #---------------------
        self.comm_choice:Tuple = (None, None)
        self.communications = [t.value for t in ThingCommType]
        self.comm_options = {}
        self.test_results = ""
        

    def tab(self)->sg.Tab:
        self._tab:sg.Tab = sg.Tab(
                self.step_id, 
                [
                    [sg.Text("With this step we will choose preferred communication method to update our Thing")],
[sg.Text(f"Communication type to use:"), sg.Combo(self.communications, default_value=self.comm_choice[0], enable_events=True, key="communication_type"),
sg.Text(f"Choose communication:"), sg.Combo(list(self.comm_options.keys()), default_value=self.comm_choice[1], disabled=len(self.comm_options)==0, enable_events=True, key="comm_options")],
                    [sg.Multiline(size=(70,20), default_text=self.test_results, background_color="black", text_color="yellow", key="test_connection_result", expand_x=True, expand_y=True, disabled=len(self.test_results)==0)],
                    [sg.Button("Test connection", key="Test communication", disabled=self.state==StepState.EXECUTION), 
                    sg.Button("Proceed to Next", key=f"{self.step_id}|Proceed to next step", disabled=self.state!=StepState.EXECUTIONSUCCES)]
                ],
                disabled=not self.is_active
            )
        return self._tab

    def delegates(self)->Dict[str, Callable]:
        ''' for each tab we need dict of event handlers '''
        return {
            "communication_type": self.change_comm_type,
            "comm_options": self.change_comm_option,
            "Test communication": self.test_communication,
            f"{self.step_id}|Proceed to next step": self.next_step,
        }

    def change_comm_type(self, event_values):
        _top_logger.debug(event_values)
        chosen_types = [t for t in ThingCommType if t.value == event_values["communication_type"]]
        if len(chosen_types) != 1:
            raise ValueError(f"Unsupported communication type {event_values['communication_type']}")
        comm_type:ThingCommType = chosen_types[0]
        try:
            if self._navigator.thingcomm_client:
                    self._navigator.thingcomm_client.disconnect()
        except Exception as e:
            _top_logger.debug(f"FAIL to close current connection with exception {e}")
        self._navigator.thingcomm_client = ThingCommFactory.client_with(
            comm_type=comm_type,
            options={
                "project_config": self.project_config.config_data
            }
        )
        # get_comm_options can have very different time (for IP it'll require network scan)
        # So our implementation is NOT client agnostic
        if comm_type == ThingCommType.IP:
            # we'll through a command in the service window
            self._state = StepState.EXECUTION
            res = CommandToExecute(
                self.networkscan_command,
                self.change_comm_type_completed,
                # cwd=self.cloud_infra_path.resolve()
            )
            self.comm_choice = (comm_type.value, None)
            return res
        self.comm_options = self._navigator.thingcomm_client.get_comm_options()
        self.comm_choice = (comm_type.value, None)
        self._state = StepState.EXECUTIONSUCCES
        return self._navigator.root()

    def change_comm_type_completed(self, **kwargs):
        ''' '''
        with open(Path(self.TEMP_IP_SCAN_FILE), "r") as f:
            self.comm_options = json.load(f)
        # let's remove temp file
        try:
            Path(self.TEMP_IP_SCAN_FILE).unlink(missing_ok=True)
        except Exception as e:
            _top_logger.warning(f"FAIL to delete temp ip-scan results file with exception {e}")
        self._state = StepState.EXECUTIONSUCCES
        return self._navigator.root()

    def change_comm_option(self, event_values):
        ''' invoked when selector for comm option was used '''
        _top_logger.debug(event_values)
        self.comm_choice = (self.comm_choice[0], event_values["comm_options"])
        try:
            res = self._navigator.thingcomm_client.connect(**self.comm_options[self.comm_choice[1]])
            self.test_results += f"\nConnect response:\n{res}\n"
        except Exception as e:
            res = None
            self.test_results += f"\nFAIL to connect with exception {e}"
        return self._navigator.root()

    def skip_sources_update(self, event_values):
        self._state = StepState.EXECUTIONSUCCES
        return self._navigator.root()

    def test_communication(self, event_values):
        # we need to verify that chosen communication method is available
        self.test_results = self._navigator.thingcomm_client.test_connection()
        return self._navigator.root()
    
