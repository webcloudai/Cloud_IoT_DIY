'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from typing import Dict
import json
from boto3 import session

import sys
import subprocess
import shutil
from pathlib import Path
import argparse
import logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
    _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))

#-------------------------
from _prepare_bootstrap import _prepare_bootstrap
from _remove_bootstrapped import _remove_bootstrapped
from common_project_config import ProjectConfig


# NOTE: Current implementation do not preserve previous builds and deployments!
# create build version from datetime (if needed) - NOT SUPPORTED FOR NOW
# create current build subfolder - NOT SUPPORTED FOR NOW

def parse_arguments():
    ''' this is required ONLY if command line is used '''
    parser = argparse.ArgumentParser(
        description="Pre-deploy and Post-destroy helper script",
        usage=''' python3 pre_deploy.py --deploy {'--verbose'}'''
    )
    parser.add_argument("--deploy", "-dp", dest="boto3_deploy", action="store_true", required=False, help="Create required pre-deploy resources with boto3")    
    parser.add_argument("--destroy", "-ds", dest="boto3_destroy", action="store_true", required=False, help="Remove pre-deployed resources")    

    args = parser.parse_args()
    return args



if __name__=="__main__":

    # parse and collect command line arguments
    my_args = parse_arguments()
    _top_logger.debug(my_args)

    #*****************************************
    #* Load Project Configuration
    pr_config = ProjectConfig.create_from_file()
    _top_logger.debug(f"Collected project config:\n{json.dumps(pr_config.config_data, indent=3)}")
    
    # we'll use boto3 session to support profiles
    cloud_session = session.Session(
        profile_name=pr_config.environment["profile"],
        region_name=pr_config.environment["region"]
    )

    mtlsapi_truststore_local_folder = Path(pr_config.mtlsapi_mythings_location) / pr_config.mtlsapi_truststoreprefix

    if my_args.boto3_deploy:
        _top_logger.info(f"Perform 'one-time' bootstrapping with boto3")
        bootstr_result = _prepare_bootstrap(
            session=cloud_session,
            iot_account_id=pr_config.environment["account"],
            default_group_name=pr_config.things_group_name,
            default_group_description=f"default group for {pr_config.mqtt_app_name}",
            default_thing_type_name=pr_config.iot_default_thing_type,
            default_thing_type_description=f"default thing type used by 'just provisioned' things for {pr_config.mqtt_app_name}",
            local_bootstrapcert_folder=Path(pr_config.bootstrapcert_local_folder),
            local_trusted_store_path=mtlsapi_truststore_local_folder / pr_config.mtlsapi_truststore_name,
            bootstrap_policy_name=pr_config.iot_bootstrapping_role_name,
            bootstrap_template_name=pr_config.iot_provisioning_template_name,
            tags=pr_config.proj_tags
        )
        if bootstr_result is None:
            _top_logger.warning(f"\n\nUnsuccessful pre-bootstrapping! {pr_config.things_group_name} group was already created.\n")
            exit(1)
    elif my_args.boto3_destroy:
        _top_logger.info(f"Remove 'one-time' bootstrapped resources with boto3")
        bootstr_result = _remove_bootstrapped(
            session=cloud_session,
            default_group_name=pr_config.things_group_name,
            local_bootstrapcert_folder=Path(pr_config.bootstrapcert_local_folder),
            local_trusted_store_path=mtlsapi_truststore_local_folder / pr_config.mtlsapi_truststore_name,
            bootstrap_policy_name=pr_config.iot_bootstrapping_role_name,
        )
    else:
        _top_logger.info(f"You should provide either --deploy or --destroy option")

