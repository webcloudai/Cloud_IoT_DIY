'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable
import PySimpleGUI as sg
import json
from pathlib import Path

from enum import Enum

#--- Proprietary modules
from cloud_client import AwsCloudClient, CloudClient
from process_ui.data_model import StepState, DataModel, CommandToExecute
from process_ui.process_navigator import ProcessNavigator, StepController
from project_deployment.steps import Step



#####################################################################
# Step 4. Update firmware and UI with cloud-specific parameters
class UpdateSourcesStepController(StepController):
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.UpdateSources.value
        # 
        self.run_command = f''

    def tab(self)->sg.Tab:
        self._tab:sg.Tab = sg.Tab(
                self.step_id, 
                [
                    [sg.Text("With this step we will update firmware and UI sources with configuration and cloud backend data")],
                    # [sg.Text("You can find detail in AWS documentation at")],
                    # [sg.InputText("https://docs.aws.amazon.com/cdk/v2/guide/cli.html#cli-deploy", size=(60,10), use_readonly_for_disable=True, disabled=True, key=str(uuid4()))],
                    # # [sg.Text(, text_color="cyan", font="Arial 11 underline")],
                    # [sg.Text(f"We'll just run for you the command")],
                    # [sg.Text(self.run_command, font="Arial 12 bold")],
                    # [sg.Output(size=(60,15))],          # an output area where all print output will go]
                    [
                        sg.Button("Run", key="Run sources update", disabled=self.state==StepState.EXECUTION), 
                        sg.Button("Skip", key="Skip sources update", disabled=self.state==StepState.EXECUTION),
                        sg.Button("Proceed to Next", key=f"{self.step_id}|Proceed to next step", disabled=self.state!=StepState.EXECUTIONSUCCES)
                    ],
                ],
                disabled=not self.is_active
            )
        return self._tab

    def delegates(self)->Dict[str, Callable]:
        ''' for each tab we need dict of event handlers '''
        return {
            "Run sources update": self.run_sources_update,
            f"{self.step_id}|Proceed to next step": self.next_step,
            "Skip sources update": self.skip_sources_update
        }

    def skip_sources_update(self, event_values):
        self._state = StepState.EXECUTIONSUCCES
        return self._navigator.root()

    def run_sources_update(self, event_values):
        # we need to update/clear two components
        # 1. In the Firmware we need to create/update src/projectData.hpp
        # 2. In the Website we need to create/update lib/projectData.dart
        # for both updates we'll be using .jinja templates
        # so to generalize the process we'll be just scan mentioned folders for .jinja templates
        # and generate files with that templates
        self._state = StepState.EXECUTION
        res = CommandToExecute(
            self.run_command,
            self.sources_update_completed,
            # cwd=self.cloud_infra_path.resolve()
        )
        return res
    
    def sources_update_completed(self, **kwargs):
        ''' delegate to be called when service window closed'''
        self._state = kwargs.get("state", StepState.EXECUTIONSUCCES)
        # return top model to rerender the window
        return self._navigator.root()
