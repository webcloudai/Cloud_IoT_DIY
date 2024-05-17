'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable
import PySimpleGUI as sg
import json
from pathlib import Path
from queue import Queue
import threading
import logging
from uuid import uuid4
_top_logger = logging.getLogger(__name__)

#--- Proprietary modules
# from cloud_client import AwsCloudClient, CloudClient
from process_ui.process_navigator import ProcessNavigator, StepController
from process_ui.data_model import StepState, DataModel, CommandToExecute
from thing_prov.steps import Step
from thingcomm_client import ThingCommClient, ThingCommFactory, ThingCommType
from mqtt_client.mqtt_client import MqttClient
from mqtt_client.mqtt_fleet_prov import FleetProv, ThingFleetProvParams


#####################################################################
# Step 2. Configure and provision the Thing
class ThingConfigStepController(StepController):
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.ThingConfig.value
        self.model_data:DataModel = self._navigator.data
        self.model_data.load_model_data()
        self.config_data = self.model_data.config_data()
        self.project_config = self.model_data.project_config or self.model_data.assemble_project_config()
        self.field_delegates = {}
        # support for background process
        self._navigator.background_process_completion_queue = Queue()

        # TEMMMMPPPPP
        building_id = "b001"
        location_id = "r003"
        thing_name = str(uuid4())

        self.prov_data = {
            "FLEET": {
                "ThingName": thing_name,
                "ThingGroup": "any",
                "ThingType": "any",
                "ThingBuilding": building_id,
                "ThingLocation": location_id,
                "MqttUrl": self.project_config.mqtt_url,
                "ApiUrl": f"{self.project_config.mtlsapi_subdomain}.{self.project_config.domain_name}"
            }        
        }
        self.prov_data["THING"] = self.prov_data["FLEET"]
        self.execution_log:str = ""
        self.log_element_key_base = "prov_exec_log"
        #-----------------------------------------------
        # mqtt related properties
        # self.thingfleet_prov:FleetProv = None
        # self.comm_queue


    def tab(self)->sg.Tab:
        ''' '''
        def render(source, level:int=0, prefix:str='')->Dict[str,any]:
            res = {}
            if isinstance(source, dict):
                for k,v in source.items():
                    if k=="_description":
                        continue
                    if isinstance(v, dict):
                        res[f"{'--'*level}{k}"] = None
                        res = {**res, **render(v, level+1, prefix=f"{prefix}{k}^")}
                    else:
                        res[f"{'  '*level}{prefix}{k}"] = v
            else:
                raise ValueError(f"Only dicts are supported in config for now")
            return res

        def create_rows(prerendered:dict, event_prefix:str)->List[List[sg.Element]]:
            ''' '''
            res = []
            for k,v in prerendered.items():
                event_key =f"{event_prefix}{k}"
                row = [sg.Text(k, size=(30,1))]
                r_values = self.cloud.available_values_for(k.strip().split("^")[-1].strip(), v)
                if r_values is None:
                    if v is None:
                        pass #row.append()
                    else:
                        row.append(sg.InputText(v, disabled="description" in k, size=(70,1), key=event_key))#, background_color="brown" if "description" in k else "white"))
                        self.field_delegates[event_key] = self.field_update
                elif isinstance(r_values, list):
                    self.field_delegates[event_key] = self.field_update
                    row.append(
                        sg.Combo(r_values, default_value=v if v in r_values else None, enable_events=True, key=event_key, background_color="white") #"choose_hosted_zone")
                    )
                else:
                    # not a list - just a value
                    self.field_delegates[event_key] = self.field_update
                    row.append(sg.InputText(r_values, disabled=True, size=(50,1), key=event_key))#, background_color="white",))

                res.append(row)
            res.append(
                [
    sg.Multiline(size=(70,20), default_text=self.execution_log, background_color="black", text_color="yellow", key=f"{event_prefix}{self.log_element_key_base}", expand_x=True, expand_y=True, disabled=len(self.execution_log)==0)
                ]
            )
            res.append(
                [
                    # sg.Button(f"Start {event_prefix[:-1]} provisioning", key=f"{event_prefix}Save configuration", disabled=min([len(v) for v in self.prov_data[event_prefix[:-1]].values()])>0),
                    sg.Button(f"Start {event_prefix[:-1]} provisioning", key=f"{event_prefix}Save configuration", disabled=min([len(v) for v in self.prov_data[event_prefix[:-1]].values()])==0),
                    sg.Button("Proceed to Verification", key=f"{event_prefix}Proceed to next step", disabled=False)
                ]
            )
            return res

        if self._navigator.background_process_message:
            if "FAIL" in self._navigator.background_process_message:
                self.state = StepState.EXECUTIONFAILED
            else:
                self.state = StepState.EXECUTIONSUCCES
        rendered_tab1 = render(self.prov_data["FLEET"])
        rendered_tab2 = render(self.prov_data["THING"])

        self._tab:sg.Tab = sg.Tab(
            self.step_id,
            [[
                sg.TabGroup(
                    [[
                        sg.Tab("Fleet provisioning", 
                            [[sg.Column(
                                create_rows(rendered_tab1, event_prefix="FLEET|"),
                                # size=(100,50),
                                size_subsample_width=1.1,
                                size_subsample_height=1.1,
                                # scrollable=True
                            )]],
                            key="Required parameters",
                            expand_y=True,
                            expand_x=True,
                        ),
                        sg.Tab("Thing provisioning",
                            [[sg.Column(
                                create_rows(rendered_tab2, event_prefix="THING|"),
                                size_subsample_width=1.1,
                                size_subsample_height=1.1,
                            )]],
                            key="Optional parameters",
                            expand_y=True,
                            expand_x=True,
                        )
                    ]],
                    visible=True,
                    expand_x=True,
                    expand_y=True,
                    
                )
            ]],
            disabled = not self.is_active,
            key="Collect parameters"
        )
        return self._tab

    def delegates(self)->Dict[str, Callable]:
        ''' for each tab we need dict of event handlers '''
        return {
            **self.field_delegates,
            **{
                "FLEET|Proceed to next step": self.next_step,
                "FLEET|Save configuration": self.fleet_provisioning,
                "THING|Proceed to next step": self.next_step,
                "THING|Save configuration": self.thing_provisioning
            }
        }

    def _claim_cert_and_keys(self)->Dict[str,str]:
        ''' Returns claim Cert and Keys with key names exactly as Thing expected '''
        result = {
            "ClaimCert": "",
            "ClaimKeys": ""
        }
        newest_cert_p:Path = sorted([v for v in Path(self.project_config.bootstrapcert_local_folder).glob("*.cert.pem")], key=lambda x: x.stat().st_mtime)[-1]
        newest_keys_p:Path = newest_cert_p.with_stem(newest_cert_p.stem.replace(".cert",".keys"))
        # NOTE that we need to replace '/n' with some character not in base64 encoding for Serial comm
        # replacing back will be the responsibility of the Thing
        with open(newest_cert_p,"r") as f:
            result["ClaimCert"] = f.read().replace("\n","|")
        with open(newest_keys_p, "r") as f:
            result["ClaimKeys"] = f.read().replace("\n","|")
        return result


    def fleet_provisioning(self, values):
        ''' this will just push collected parameters AND claim cert/keys to device '''
        # let's update values first
        self.field_update(values=values)
        self._navigator.logs_element_name = f"FLEET|{self.log_element_key_base}"
        cl:ThingCommClient = self._navigator.thingcomm_client
        self.execution_log += f"\nSending this fleet configuration data to device:\n{json.dumps(self.prov_data['FLEET'], indent=3)}\n"
        # Full fleet data should include claim certificate and keys!
        full_data = {**self.prov_data["FLEET"], **self._claim_cert_and_keys()}
        self.process_thread = threading.Thread(
            target=cl.send_form_data, 
            args=(
                full_data,
                self.fleet_prov_logs_callback
            ) #(self.command_process.stdout, self.command_output_queue)
        )
        self.process_thread.start()
        # Provisioning executed in background thread
        # Notification will be handled through queue and Navigator
        return self._navigator.root()
        # sync solution below leaves UI w/o updates
        # cl:ThingCommClient = self._navigator.thingcomm_client
        # self.execution_log += f"\nSending this fleet configuration data to device:\n{json.dumps(self.prov_data['FLEET'], indent=3)}\n"
        # resp = cl.send_form_data(data=self.prov_data["FLEET"])
        # self.execution_log += "Received response from device:\n"
        # self.execution_log += f"{resp}\n"
        # return self._navigator.root()

    def fleet_prov_logs_callback(self):
        self.execution_log = "\n".join(self._navigator.thingcomm_client._logs)
        self._navigator.current_window[self._navigator.logs_element_name].update(self.execution_log, append=False, autoscroll=True)
        self._navigator.current_window.Refresh()


    def thing_provisioning(self, values):
        ''' FOR NOW
            Just one option available - running same fleet provisioning flow from the laptop
            OPTION to use cloud client for provisioning is TODO <<<<<==================
        '''
        self._state = StepState.EXECUTION
        self._navigator.logs_element_name = f"THING|{self.log_element_key_base}"
        self.thingfleet_prov = FleetProv(
            self.project_config, ThingFleetProvParams(**self.prov_data["THING"], commQueue = self._navigator.background_process_completion_queue)
        )
        self.thingfleet_prov.log_callback = self.thingfleet_prov_logs_callback
        # self.thingfleet_prov.log_queue = None #self._navigator.logs_queue
        # if not self.thingfleet_prov.provision():
        #     _top_logger.error(f"Thing provisioning failed")
        # self._navigator.logs_queue = None
        # self._navigator.logs_element_name = None
        self.process_thread = threading.Thread(
            target=self.thingfleet_prov.provision(), 
            args=() #(self.command_process.stdout, self.command_output_queue)
        )
        self.process_thread.start()
        # Provisioning executed in background thread
        # Notification will be handled through queue and Navigator
        return self._navigator.root()

    # self.thingfleet_prov.mqtt_client.cert_req_response['privateKey']
    # self.thingfleet_prov.mqtt_client.cert_req_response['certificatePem']

    def thingfleet_prov_logs_callback(self):
        self.execution_log = "\n".join(self.thingfleet_prov._logs)
        # execution_log = "\n".join(self.thingfleet_prov._logs)
        # self._navigator.logs_queue.put_nowait(self.execution_log)
        self._navigator.current_window[self._navigator.logs_element_name].update(self.execution_log, append=False, autoscroll=True)
        self._navigator.current_window.Refresh()

    def field_update(self, values):
        # decode config part changed from event name
        event_n = values["__event_name"].split("|")
        # update all fields for that config part
        for k,v in values.items():
            if not isinstance(k,str) or not k.startswith(event_n[0]):
                continue
            k_route = k.split("|")
            if k_route[1] not in self.prov_data[k_route[0]]:
                continue
            self.prov_data[k_route[0]][k_route[1]] = v
        return self._navigator.root()
