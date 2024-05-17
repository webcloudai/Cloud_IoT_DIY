from typing import Dict
import json


class ProvisioningTemplate:
    ''' '''
    @staticmethod
    def templates(groupName:str="*", account_allowed:str=None, thing_policy_name:str=None, topics_allowed:list=None)->Dict[str,Dict]:
        all_templates = {
        "*": {
                "Parameters":{
                    "AWS::IoT::Certificate::Id": { "Type":"String" },
                    "appName": { "Type" : "String" },
                    "thingName" : { "Type" : "String" },
                    "thingSerial" : { "Type" : "String" },
                    "thingGroup" : { "Type" : "String" },
                    "thingType" : { "Type" : "String" },
                    "buildingId" : { "Type" : "String" },
                    "locationId" : { "Type" : "String" },
                },
                "Resources":{
                    "thing": {
                        "Type":"AWS::IoT::Thing",
                        "Properties":{
                            "ThingName":{ "Ref":"thingName" },
                            # "AttributePayload":{
                            #     "version":"v1",
                            #     "serialNumber":{  "Ref":"thingSerial" }
                            # },
                            "ThingTypeName":{  "Ref":"thingType" },
                            "ThingGroups":[
                                # { "Ref":"appName" },
                                { "Ref":"thingGroup" }
                            ],
                            # "BillingGroup": { "Ref":"appName" }
                        },
                        "OverrideSettings" : {
                            "AttributePayload" : "MERGE",
                            "ThingTypeName" : "REPLACE",
                            "ThingGroups" : "DO_NOTHING"
                        }
                    },
                    "certificate": {
                        "Type":"AWS::IoT::Certificate",
                        "Properties":{
                            "CertificateId":{ "Ref":"AWS::IoT::Certificate::Id" },
                            "Status":"ACTIVE"
                        }
                    },
                    "policy": {
                        "Type": "AWS::IoT::Policy",
                        "Properties": {
                            "PolicyName": thing_policy_name
                        }
                    }
                    # "policy":{
                    #     "Type":"AWS::IoT::Policy",
                    #     "Properties":{
                    #         "PolicyDocument":"{ \"Version\": \"2012-10-17\", \"Statement\": [{ \"Effect\": \"Allow\", \"Action\":[\"iot:Publish\"], \"Resource\": [\"arn:aws:iot:us-east-1:123456789012:topic/foo/bar\"] }] }"
                    #     }
                    # }
                }
            }
        }
        return all_templates[groupName]

    # @staticmethod
    # def templateForGroup(groupName:str=None, account:str=None, thing_policy_name:str=None, topics:list=None)->str:
    #     ''' '''
    #     # scaffolded implementation (to be extended to support different templates)
    #     # return json.dumps(ProvisioningTemplate.templates["*"])

    @staticmethod
    def templateForGroup(groupName:str, account:str=None, thing_policy_name:str=None, topics:list=None)->str:
        ''' '''
        # scaffolded implementation (to be extended to support different templates)
        templ = ProvisioningTemplate.templates("*", thing_policy_name=thing_policy_name, account_allowed=account, topics_allowed=topics)
        print(json.dumps(templ, indent=3))
        return json.dumps(templ)