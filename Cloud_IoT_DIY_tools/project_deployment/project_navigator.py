'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable
from uuid import uuid4
from pathlib import Path
import json

#--- Proprietary modules
from process_ui.data_model import StepState, DataModel
from process_ui.process_navigator import ProcessNavigator, StepController
from project_deployment.steps import Step
from project_deployment.prerequisites_step import PrerequisitesStepController
from project_deployment.configuration_step import ProjectConfigStepController
from project_deployment.deploycloud_step import DeployCloudBackendStepController
from project_deployment.updatesources_step import UpdateSourcesStepController
from project_deployment.updatecloud_step import UpdateCloudStepController
from project_deployment.project_data_model import AppDataModel


####################################################################
#* Top-level Navigator
class AppProcessNavigator(ProcessNavigator):
    def __init__(self, data:DataModel=None, navigator_id: str = f"app|model|{uuid4()}", parent_navigator:ProcessNavigator=None) -> None:
        super().__init__(data=data, navigator_id=navigator_id, parent_navigator=parent_navigator)
        #--------- Project Data Model init
        self.data:AppDataModel = self.data or data or AppDataModel()
        #--------- Process definition
        self.steps:Dict[str, StepController] = {
            Step.Prerequisites.value: PrerequisitesStepController(navigator=self),
            Step.ProjectConfig.value: ProjectConfigStepController(navigator=self),
            Step.DeployCloudBackend.value: DeployCloudBackendStepController(navigator=self),
            Step.UpdateSources.value: UpdateSourcesStepController(navigator=self),
            Step.UpdateCloud.value: UpdateCloudStepController(navigator=self)
        }

