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
# Step 5. Deploy updates to the cloud backend
#   This may be required if UI was updated
class UpdateCloudStepController(StepController):
    def __init__(self, navigator:ProcessNavigator, **kwargs) -> None:
        super().__init__(navigator=navigator, **kwargs)
        self._step_id = Step.UpdateCloud.value
        # self.run_command = ["cdk", "synth", "--verbose", f"--profile {self.cloud.profile_name}"]
        cdk_out_path:Path = self._navigator.data.instance_config['_cdk_deploy_output_path']
        # we don't need profile info as ENV is included to project config but we may need ut if current default doesn't have permissions to deploy in that account/region
        self.prepare_command = f"flutter build web"
        self.run_command = f'python lbuild.py --deploy " --verbose --outputs-file '+f"'{cdk_out_path}'"+f' --require-approval never'# --profile {self.cloud.profile_name}"' 
        self.run_command += f' --profile {self.cloud.profile_name}"' if self.cloud.profile_name!="default" else '"'

        self.cloud_infra_path = Path("../Cloud_IoT_DIY_cloud")
        self.cloud_infra_venv = ".infra_venv/bin/activate"

    def tab(self)->sg.Tab:
        self._tab:sg.Tab = sg.Tab(
                self.step_id, 
                [
                    [sg.Text("With this step we will re-build UI and re-deploy Cloud Backend Stack with AWS CDK")],
                    [sg.Text("We may need to do it as UI was updated after first cloud deployment")],
                    # [sg.InputText("https://docs.aws.amazon.com/cdk/v2/guide/cli.html#cli-deploy", size=(60,10), use_readonly_for_disable=True, disabled=True, key=str(uuid4()))],
                    # [sg.Text(, text_color="cyan", font="Arial 11 underline")],
                    [sg.Text(f"We'll just run for you the commands")],
                    [sg.Text(self.prepare_command, font="Arial 12 bold")],
                    [sg.Text(self.run_command, font="Arial 12 bold")],
                    # [sg.Output(size=(60,15))],          # an output area where all print output will go]
                    [
                        sg.Button("Run", key="Run redeployment", disabled=self.state==StepState.EXECUTION), 
                        sg.Button("Skip", key="Skip redeployment", disabled=self.state==StepState.EXECUTION),
                        sg.Button("Proceed to Next", key=f"{self.step_id}|Proceed to next step", disabled=self.state!=StepState.EXECUTIONSUCCES)
                    ],
                ],
                disabled=not self.is_active
            )
        return self._tab

    def delegates(self)->Dict[str, Callable]:
        ''' for each tab we need dict of event handlers '''
        return {
            "Run redeployment": self.run_cdk_redeploy,
            f"{self.step_id}|Proceed to next step": self.next_step,
            "Skip redeployment": self.skip_cdk_redeploy
        }

    def skip_cdk_redeploy(self, event_values):
        self._state = StepState.EXECUTIONSUCCES
        return self._navigator.root()

    def run_cdk_redeploy(self, event_values):
        self._state = StepState.EXECUTION
        res = CommandToExecute(
            # f"cd '{self.cloud_infra_path.absolute()}'; source '{self.cloud_infra_venv.absolute()}'; " + self.run_command,
            f"source '{self.cloud_infra_venv}'; " + self.run_command,
            self.cdk_redeploy_completed,
            cwd=self.cloud_infra_path.resolve())
        return res
    
    def cdk_redeploy_completed(self, **kwargs):
        ''' delegate to be called when service window closed'''
        self._state = kwargs.get("state", StepState.EXECUTIONSUCCES)
        # return top model to rerender the window
        return self._navigator.root()
