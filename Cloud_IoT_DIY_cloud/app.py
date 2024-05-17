'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from typing import Dict
import json
from pathlib import Path
import aws_cdk as cdk
import sys
from jinja2.nativetypes import NativeEnvironment
from common_project_config import ProjectConfig


import logging
# Setup logging.
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))

from cloud_iot_diy_cloud.cloud_iot_diy_cloud_stack import CloudIoTDiyCloudStack


#*****************************************
#* Collect Project Configuration
pr_config = ProjectConfig.create_from_file()    #! NOTE that NOT ALL config sections are jinja rendered by default!
_top_logger.info(f"Collected parameters for stack:\ndomain_name:{pr_config.domain_name}\nhosted_zone_id:{pr_config.hosted_zone_id}\nhosted_zone_name:{pr_config.hosted_zone_name}")
_top_logger.info(json.dumps(pr_config.config_data, indent=3))
#-------- add collected environment information
# If you don't specify 'env', this stack will be environment-agnostic.
# For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
# stack_params = {
#     **pr_config.config_data,
#     **{ "env": cdk.Environment(account=pr_config.environment["account"], region=pr_config.environment["region"]) }
# }
# _, _, _ = stack_params.pop("domain", None), stack_params.pop("project_subdomain", None), stack_params.pop("my_things", None)
#---- define stack name
stack_name = pr_config.environment["stack_name_root"] + pr_config.environment["region"].replace("-","") # (region.replace("-","") if region!="us-east-1" else "")

#*****************************************
#* Init App
app = cdk.App()

#*****************************************
#* Init Stack
project_stack = CloudIoTDiyCloudStack(app, stack_name, pr_config, env=cdk.Environment(account=pr_config.environment["account"], region=pr_config.environment["region"]))
# project_stack = CloudIoTDiyCloudStack(app, stack_name, **stack_params)

#*****************************************
# Tag the whole Stack (tags will be added to every taggable resource in the stack)
# *NOTE* this is important - we'll be able to identify orphan resources when/if stack destroy will not delete everything!
for t_name, t_value in pr_config.proj_tags.items():
    cdk.Tags.of(project_stack).add(t_name, t_value, priority=100)
#*****************************************

app.synth()

