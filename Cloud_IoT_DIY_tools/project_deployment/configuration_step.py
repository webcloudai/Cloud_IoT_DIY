'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable
import PySimpleGUI as sg
import json
from pathlib import Path

import logging
_top_logger = logging.getLogger(__name__)

#--- Proprietary modules
from cloud_client import AwsCloudClient, CloudClient
from process_ui.process_navigator import ProcessNavigator, StepController
from process_ui.data_model import StepState, DataModel
from project_deployment.steps import Step


#####################################################################
# Step 2. Configure project
class ProjectConfigStepController(StepController):
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.ProjectConfig.value
        self.model_data:DataModel = self._navigator.data
        self.model_data.load_model_data()
        self.field_delegates = {}

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
                    sg.Button("Save configuration and update .gitignore", key=f"{event_prefix}Save configuration", disabled=self.state!=StepState.EXECUTION),
                    sg.Button("Proceed to Deploy", key=f"{event_prefix}Proceed to next step", disabled=False)
                ]
            )
            return res

        config = self.model_data.config_data()
        rendered_required = render(config.get("REQUIRED", {}))
        rendered_optional = render(config.get("OPTIONAL", {}))

        self._tab:sg.Tab = sg.Tab(
            self.step_id,
            [[
                sg.TabGroup(
                    [[
                        sg.Tab("Required parameters", 
                            [[sg.Column(
                                create_rows(rendered_required, event_prefix="REQUIRED|"),
                                # size=(100,50),
                                size_subsample_width=1.1,
                                size_subsample_height=1.1,
                                # scrollable=True
                            )]],
                            key="Required parameters",
                            expand_y=True,
                            expand_x=True,
                        ),
                        sg.Tab("Optional parameters",
                            [[sg.Column(
                                create_rows(rendered_optional, event_prefix="OPTIONAL|"),
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
                "REQUIRED|Proceed to next step": self.next_step,
                "REQUIRED|Save configuration": self.save_config,
                "OPTIONAL|Proceed to next step": self.next_step,
                "OPTIONAL|Save configuration": self.save_config
            }
        }

    def save_config(self, values):
        self.model_data.save_model_data()
        self.model_data.update_local_file(type="gitignore")
        return None

    def field_update(self, values):
        self._state = StepState.EXECUTION
        # _top_logger.debug(values)
        # decode config part changed from event name
        event_n = values["__event_name"].split("|")
        # update all fields for that config part
        for k,v in values.items():
            if not isinstance(k,str) or not k.startswith(event_n[0]):
                continue
            k_route = k.split("|")
            config_route = [k_route[0]]
            config_route.extend(k_route[1].strip().split("^"))
            self.model_data.update_by_parameter_route( route=config_route, value=v )
        # self.model_data.update_by_parameter_route( route=config_route, value=values[values["__event_name"]] )
        return self._navigator.root()
