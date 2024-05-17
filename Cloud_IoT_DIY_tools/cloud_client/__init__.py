'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Union
from abc import ABC, abstractmethod
from uuid import uuid4
# This maybe changed to lazy import if other clouds supported
from boto3 import s3, session

import logging
_top_logger = logging.getLogger(__name__)

###########################################################
# Abstract Base Class for Cloud Client definition
class CloudClient(ABC):

    @classmethod
    def create_with_profile(cls, *, profile_name:str=None, region:str=None):
        return cls(profile_name=profile_name, region=region)

    def __init__(self, *, profile_name:str=None, region:str=None) -> None:
        ''' '''
        self.profile_name = None
        
        self.cloud_session = None
        self.sts_client = None
        self.account_id = None
        self.iam_client = None
        self.account_alias = None

        self.region = None
        self.regions = None
        self.profile = None
        self.profiles = None

        self.hosted_zone = None

    @abstractmethod
    def available_values_for(self, cloud_param:str)->List[str]:
        ''' '''

###########################################################
# AWS client (boto3 based)
class AwsCloudClient(CloudClient):
    def __init__(self, *, profile_name:str=None, region:str=None) -> None:
        ''' '''
        self._profile_name = profile_name
        self.cloud_session = session.Session(profile_name=profile_name, region_name=region)
        self.profile_name = self.cloud_session.profile_name
        self.sts_client = self.cloud_session.client("sts")
        self.account_id = self.sts_client.get_caller_identity().get("Account",None)
        self.iam_client = self.cloud_session.client("iam")
        self.account_alias = self.iam_client.list_account_aliases().get("AccountAliases",[""])[0]
        self.route53_client = self.cloud_session.client("route53")
        # self.route53domains_client = self.cloud_session.client('route53domains')

        self.region = self.cloud_session.region_name
        self.regions = self.cloud_session.get_available_regions("iot")
        self.profile = self.cloud_session.profile_name
        self.profiles = self.cloud_session.available_profiles


    def available_values_for(self, cloud_param:str, options=None)->Union[List[str],str]:
        ''' '''
        if cloud_param=="hosted_zone_name":
            # up to 100 hosted zones
            response = self.route53_client.list_hosted_zones()
            hosted_zones = {v.get("Id",str(uuid4())):v.get("Name","---") for v in response.get("HostedZones",[])}
            if isinstance(options, str):
                try:
                    hz_id = [k for k,v in hosted_zones.items() if v==options][0]
                    hz_response = self.route53_client.get_hosted_zone(Id=hz_id)
                    self.hosted_zone = hz_response.get("HostedZone", None)
                except:
                    self.hosted_zone = None
            return list(hosted_zones.values())
        elif cloud_param=="hosted_zone_id":
            # id will be defined by hosted zone name 
            if isinstance(self.hosted_zone, dict):
                return self.hosted_zone.get("Id","???").replace('/hostedzone/','')
        elif cloud_param=="domain":
            if isinstance(self.hosted_zone, dict):
                res = []
                paginator = self.route53_client.get_paginator('list_resource_record_sets')
                try:
                    source_zone_records = paginator.paginate(HostedZoneId=self.hosted_zone["Id"])
                    for record_set in source_zone_records:
                        for record in record_set['ResourceRecordSets']:
                            if record['Type'] == "A": #'CNAME':
                                res.append(record['Name'][:-1])
                    return res
                except Exception as e:
                    _top_logger.error(f"Fail to get source zone records with exception {e}")
        return None


