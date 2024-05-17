'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
import json
from pathlib import Path
from jinja2.nativetypes import NativeEnvironment
from typing import Dict, List
from pathlib import Path

import logging
_top_logger = logging.getLogger(__name__)

class ProjectConfig():
    ''' '''
    @staticmethod
    def create_from_file(
        project_config_path:Path=Path("../project_config.json"),
        jinja_sections:List[str]=["aws_iot_provisioning", "auth", "urls"]
        )->ProjectConfig:
        ''' '''
        #*****************************************
        #* Load Project Configuration
        with open(project_config_path,"r") as f:
            project_config_data = json.load(f)

        return ProjectConfig(project_config=project_config_data, jinja_sections=jinja_sections)

    @staticmethod
    def get_config_part(source:dict, key:str)->dict:
        res = source.get(key, {})
        res.pop("description", None)
        res.pop("_description", None)
        return res


    def __init__(self, project_config:dict, jinja_sections:List[str]=["aws_iot_provisioning", "auth", "urls"]) -> None:
        ''' 
            @param {dict} project_config - dictionary with all config information
            @param {List[str]} jinja_sections - list of sections to be rendered with Jinja
        '''
        #* Local locations
        mtlsapi_mythings_location = project_config.get("Local_Locations", {}).get("my_things", None)
        web_site_depl = project_config.get("Local_Locations", {}).get("web_site_depl", None)
        web_site = project_config.get("Local_Locations", {}).get("web_site", None)
        my_things = project_config.get("Local_Locations", {}).get("my_things", None)
        lambda_deployments_folder = project_config.get("Local_Locations", {}).get("lambda_deployments_folder", None)        
        firmware_folder = project_config.get("Local_Locations", {}).get("firmware_folder", None)        
        #* Deployment ENV
        profile = project_config.get("Cloud_Deployment_ENV", {}).get("depl_profile", None)
        profile = None if profile=="default" else profile
        acc = project_config.get("Cloud_Deployment_ENV", {}).get("depl_account", None)
        acc = None if acc=="default" else acc
        region=project_config.get("Cloud_Deployment_ENV", {}).get("depl_region", None)
        #* Required configuration
        required_config = project_config.get("REQUIRED", {})
        #----- Cloud
        cloud_config = ProjectConfig.get_config_part(required_config, "cloud")
        stack_name_root = cloud_config.get("stack_name_root", "diyIoT")
        hosted_zone_id = cloud_config.get("hosted_zone_id", "")
        hosted_zone_name = cloud_config.get("hosted_zone_name", "")
        _top_logger.debug(f"Will be using Hosted Zone {hosted_zone_name}({hosted_zone_id})")
        #----- URLs
        urls_config = ProjectConfig.get_config_part(required_config, "urls")  
        domain = urls_config.get('domain', '')
        project_subdomain = urls_config.get('project_subdomain', '')
        domain_name = f"{project_subdomain}.{domain}"  
        _top_logger.debug(f"Project root domain will be {domain_name}")
        #----- Assert required parameters
        if domain_name=="." or hosted_zone_id=="" or hosted_zone_name=="":
            raise ValueError(f"project_config.json must have domain_name, hosted_zone_id and hosted_zone_name")
        #*****************************************

        #*****************************************
        #* Optional configuration
        optional_config:Dict = project_config.get("OPTIONAL", {})
        optional_cloud_config:Dict = optional_config.get("cloud", {})    
        project_tags:Dict = optional_cloud_config.pop("tags",{"project": "IoT_DIY"})

        #--- Update some auth fields (transform dicts to lists, drop keys)
        auth_config = optional_config.get("auth", {})
        for k in ["auth_callback_urls", "auth_logout_urls"]:
            if k in auth_config:
                auth_config[k] = list(auth_config[k].values())

        #---- assemble optional stack params
        # NOTE: optional cloud, url, mqtt, auth and other subsections of project config 
        #       must have keys exactly like CloudIoTDiyCloudStack constructor params!
        self.config_data = {
            # **ProjectConfig.get_config_part(optional_config, "cloud"),
            **optional_cloud_config,
            **ProjectConfig.get_config_part(optional_config, "urls"),
            **ProjectConfig.get_config_part(optional_config, "mqtt"),
            **ProjectConfig.get_config_part(optional_config, "mqtt_topic"),
            **ProjectConfig.get_config_part(optional_config, "mqtt_payloads"),
            **ProjectConfig.get_config_part(optional_config, "mtls_api"),
            **ProjectConfig.get_config_part(optional_config, "storage_keys"),
            **ProjectConfig.get_config_part(optional_config, "aws_iot_provisioning"),
            **ProjectConfig.get_config_part(optional_config, "firmware"),
            **auth_config,
            **{
                "environment": {
                    "region": region,
                    "account": acc,
                    "profile": profile,
                    "stack_name_root": stack_name_root
                },
                "hosted_zone_id": hosted_zone_id,
                "hosted_zone_name": hosted_zone_name,
                "domain": domain,
                "project_subdomain": project_subdomain,
                "domain_name": domain_name,
                "web_site_depl_location":  web_site_depl,
                "web_site_location":  web_site,
                "mtlsapi_mythings_location": mtlsapi_mythings_location,
                "my_things": my_things,
                "lambda_deployments_folder": lambda_deployments_folder,
                "proj_tags": project_tags,
                "firmware_folder": firmware_folder
            }
        }
        # we need to transform some parameters provided as Jinja templates
        # aws_iot_provisioning section
        jjenv = NativeEnvironment() #undefined=DebugUndefined)
        # we'll run jinja replacement multiple times to resolve hierarchies of templates
        for iii in range(0,3):
            for section in jinja_sections:
                for k,v in ProjectConfig.get_config_part(optional_config, section).items():
                    if isinstance(v, str):
                        self.config_data[k] = jjenv.from_string(v).render(**self.config_data)
                    elif isinstance(v, list):
                        self.config_data[k] = [ jjenv.from_string(vv).render(**self.config_data) for vv in v ]

        # now we'll assign every property from collected options
        for k,v in self.config_data.items():
            setattr(self, k, v)