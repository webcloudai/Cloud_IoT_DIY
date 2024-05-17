'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable
import PySimpleGUI as sg
import json
from pathlib import Path
from uuid import uuid4
import logging
_top_logger = logging.getLogger(__name__)

#--- Proprietary modules
from cloud_client import AwsCloudClient, CloudClient
from process_ui.data_model import StepState, DataModel, CommandToExecute
from process_ui.process_navigator import ProcessNavigator, StepController
from project_deployment.steps import Step


#####################################################################
# Step 1. Prerequisites
#           it has two substeps define by PrerequisitesProcessNavigator
class PrerequisitesProcessNavigator(ProcessNavigator):
    def __init__(self, data: DataModel=None, navigator_id: str = f"{Step.Prerequisites.value}|model|{uuid4()}", parent_navigator:ProcessNavigator=None) -> None:
        super().__init__(data=data, navigator_id=navigator_id, parent_navigator=parent_navigator)
        #--------- definition
        self.steps:Dict[str, StepController] = {
            Step.PrerequisitesConfig.value: PrerequisitesConfigStepController(navigator=self),
            Step.PrerequisitesBootstrap.value: PrerequisitesBootstrapStepController(navigator=self)
        }

class PrerequisitesStepController(StepController):
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.Prerequisites.value
        self._active:bool = True     # first step is always active
        self._state = StepState.CONFIGURATION
        self._subnavigator = PrerequisitesProcessNavigator(self._navigator.data, parent_navigator=self._navigator)

    def delegates(self)->Dict[str, Callable]:
        ''' for each tab we need dict of event handlers '''
        return self._subnavigator.delegates()

class PrerequisitesConfigStepController(StepController):
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.PrerequisitesConfig.value
        self._active:bool = True     # the very first step is always active
        self._state = StepState.CONFIGURATION

    def tab(self)->sg.Tab:
        ''' '''
        # if self._tab is None:
        prof = self.cloud.profile_name
        regn = self.cloud.region
        # if self.state != StepState.COMPLETED:
        self._tab:sg.Tab = sg.Tab(
            self._step_id, 
            [
[sg.Text(f"AWS Profile in use:"), sg.Text(f"{prof}"), sg.Combo(self.cloud.profiles, default_value=prof, enable_events=True, key="profile")],
[sg.Text(f"AWS Account in use:"), sg.Text(f"{self.cloud.account_id},"), sg.Text(f"{self.cloud.account_alias},")],
[sg.Text(f"AWS Region in use:"), sg.Text(f"{regn},"), sg.Combo(self.cloud.regions, default_value=regn, enable_events=True, key="region")],
[sg.Button("Confirm cloud account and region for your cloud backend")]
            ],
            disabled=not self.is_active
        )
        # else:
        #     self._tab:sg.Tab = sg.Tab(
        #         self._step_id, 
        #         [ sg.Text(f"This step was completed!") ],
        #         disabled=True
        #     )

        return self._tab

    def delegates(self)->Dict[str, Callable]:
        ''' for each tab we need dict of event handlers '''
        return {
            # "Confirm cloud account and region for your cloud backend":self.proceed_to_next,
            "Confirm cloud account and region for your cloud backend":self.next_step,
            "profile": self.change_profile,
            "region": self.change_region
        }

    def change_region(self, event_values):
        _top_logger.debug(event_values)
        upd_region = event_values["region"]
        self._navigator.cloud_client = AwsCloudClient(profile_name=self.cloud.profile, region=upd_region)
        return self._navigator.root()
        # return self._navigator._parent


    def change_profile(self, event_values):
        _top_logger.debug(event_values)
        upd_profile = event_values["profile"]
        upd_profile = None if upd_profile=="default" else upd_profile
        self._navigator.cloud_client = AwsCloudClient(profile_name=upd_profile, region=self.cloud.region)
        return self._navigator.root()
        

    # def proceed_to_next(self, event_values):
    #     _top_logger.info(event_values)
    #     self._state = StepState.COMPLETED
    #     next_vc = self._navigator.activate_next()
    #     if next_vc is None:
    #         ''' last step completed '''
    #         return None
    #     else:
    #         return self._navigator.root()

class PrerequisitesBootstrapStepController(StepController):
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.PrerequisitesBootstrap.value
        self._active:bool = False           
        self._state = StepState.DISABLED

    def tab(self)->sg.Tab:
        ''' '''
        self.run_command = f"cdk bootstrap aws://{self.cloud.account_id}/{self.cloud.region}"
        self._tab:sg.Tab = sg.Tab(
                self.step_id, 
                [
                    [sg.Text("Required first step is bootstrapping your AWS account and region of choice for AWS CDK")],
                    [sg.Text("You can find detail in AWS documentation at")],
                    [sg.InputText("https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html", size=(60,10), use_readonly_for_disable=True, disabled=True, key=str(uuid4()))],
                    # [sg.Text(, text_color="cyan", font="Arial 11 underline")],
                    [sg.Text(f"We'll just run for you the command")],
                    [sg.Text(self.run_command, font="Arial 12 bold")],
                    # [sg.Output(size=(60,15))],          # an output area where all print output will go]
                    [
                        sg.Button("Run", key="Run CDK bootstrap", disabled=self.state==StepState.EXECUTION), 
                        sg.Button("Skip", key="Skip CDK bootstrap", disabled=self.state==StepState.EXECUTION),
                        sg.Button("Proceed to Next", key="Proceed to next step", disabled=self.state!=StepState.EXECUTIONSUCCES)
                    ],
                ],
                # key="tab|bootstrap",
                disabled=not self.is_active
            )
        return self._tab

    def delegates(self)->Dict[str, Callable]:
        ''' for each tab we need dict of event handlers '''
        return {
            "Run CDK bootstrap": self.run_cdk_bootstrap,
            "Proceed to next step": self.next_step,
            "Skip CDK bootstrap": self.skip_cdk_bootstrap
        }

    def skip_cdk_bootstrap(self, event_values):
        self._state = StepState.EXECUTIONSUCCES
        return self._navigator.root()

    def run_cdk_bootstrap(self, event_values):
        self._state = StepState.EXECUTION
        return CommandToExecute(self.run_command, self.cdk_bootstrap_completed)
        # return CommandToExecute(["ping","8.8.8.8","-c 10", ">", "&2"], self.cdk_bootstrap_completed)
    
    def cdk_bootstrap_completed(self, **kwargs):
        ''' delegate to be called when service window closed'''
        self._state = kwargs.get("state", StepState.EXECUTIONSUCCES)
        # return top model to rerender the window
        return self._navigator.root()

        