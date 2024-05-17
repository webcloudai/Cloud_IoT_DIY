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
from thing_prov.steps import Step
from thing_prov.step000_commsetup import CommSetupStepController
from thing_prov.step010_thingconfig import ThingConfigStepController
# from thing_prov.step020_provisioning import ProvisioningStepController
from thing_prov.step020_verifyprovisioning import VerifyProvisioningStepController

from thing_prov.project_data_model import AppDataModel


####################################################################
#* Top-level Navigator
class AppProcessNavigator(ProcessNavigator):
    def __init__(self, data:DataModel=None, navigator_id: str = f"app|model|{uuid4()}", parent_navigator:ProcessNavigator=None) -> None:
        super().__init__(data=data, navigator_id=navigator_id, parent_navigator=parent_navigator)
        #--------- Project Data Model init
        self.data:AppDataModel = self.data or data or AppDataModel()
        #--------- Process definition
        self.steps:Dict[str, StepController] = {
            Step.CommSetup.value: CommSetupStepController(navigator=self),
            Step.ThingConfig.value: ThingConfigStepController(navigator=self),
            # Step.Provisioning.value: ProvisioningStepController(navigator=self),
            Step.VerifyProvisioning.value: VerifyProvisioningStepController(navigator=self)
        }

