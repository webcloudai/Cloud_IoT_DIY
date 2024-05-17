'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from enum import Enum

####################################################################
#* Define our process steps and substeps
class Step(Enum):
    CommSetup = "CommSetup"                     # choose communication for device provisioning (IP/Serial/BLE)
    ThingConfig = "ThingConfig"                 # collect required Thing parameters and provision thing
    # Provisioning = "Provisioning"               # run cdk deploy and collect cloud parameters
    # ProvisioningFleet = "Provisioning|Fleet"
    # ProvisioningThing = "Provisioning|Thing"
    VerifyProvisioning = "VerifyProvisioning"   # verify that Thing was provisioned correctly

