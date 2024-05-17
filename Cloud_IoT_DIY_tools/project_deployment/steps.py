'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from enum import Enum

####################################################################
#* Define our process steps and substeps
class Step(Enum):
    Prerequisites = "Prerequisites"             # verify account, run CDK bootstrap, collect defaults, update .gitignore
    PrerequisitesConfig = "Prerequisites|Config"
    PrerequisitesBootstrap = "Prerequisites|Bootstrap"
    ProjectConfig = "ProjectConfig"             # collect all project parameters
    DeployCloudBackend = "DeployCloudBackend"   # run cdk deploy and collect cloud parameters
    UpdateSources = "UpdateSources"
    UpdateCloud = "UpdateCloud"

