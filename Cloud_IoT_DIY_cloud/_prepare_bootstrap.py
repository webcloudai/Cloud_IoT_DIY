'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from typing import Dict, List
from pathlib import Path
from uuid import uuid4
import json
import boto3
import logging
_top_logger = logging.getLogger(__name__)


def _prepare_bootstrap(
        *, 
        session:boto3.Session,
        iot_account_id:str,
        default_group_name:str,
        default_group_description:str,
        default_thing_type_name:str,
        default_thing_type_description:str,
        local_trusted_store_path:Path,
        local_bootstrapcert_folder:Path,
        bootstrap_policy_name:str,
        bootstrap_template_name:str,
        tags:Dict[str, str]
    ):
    ''' this will create 
    - default thing group
    - bootstrap certificate (trusted store to be updated and cert data stored locally)
    - iot policy for bootstrap certificate
    - attach certificate to bootstrap certificate 
    '''

    iot_client = session.client("iot")
    #-------------------------------------
    #* define default IoT Group
    # check if it doesn't exist first
    try:
        resp = iot_client.describe_thing_group( thingGroupName=default_group_name )
        resp = None if isinstance(resp, dict) and resp.get("thingGroupName","").lower()!=default_group_name.lower() else resp
    except iot_client.exceptions.ResourceNotFoundException:
        resp = None
    except Exception as e:
        _top_logger.error(f"Fail to collect IoT group {default_group_name} with exception {e}")
        raise e
    if resp is None:
        # Response syntax:
        # {
        #     'thingGroupName': 'string',
        #     'thingGroupArn': 'string',
        #     'thingGroupId': 'string'
        # }
        standard_group = iot_client.create_thing_group(
            thingGroupName= default_group_name,
            # parentGroupName= None,
            thingGroupProperties= {
                'thingGroupDescription': default_group_description,
                # 'attributePayload': {
                #     'attributes': {
                #         'string': 'string'
                #     }
                # },
                # 'merge': True|False
            },
            tags=[{"Key":k, "Value":v} for k,v in tags.items()]
        )
    else:
        _top_logger.info(f"IoT Group and other bootstrapping creation skipped as it's already available. Info: {resp}")
        return None
    #-------------------------------------
    #* define default IoT Thing Type
    # check if it doesn't exist first
    try:
        resp = iot_client.describe_thing_type( thingGroupName=default_thing_type_name )
        resp = None if isinstance(resp, dict) and resp.get("thingTypeName","").lower()!=default_thing_type_name.lower() else resp
    except iot_client.exceptions.ResourceNotFoundException:
        resp = None
    except Exception as e:
        _top_logger.error(f"Fail to collect default thing type {default_thing_type_name} with exception {e}")
        raise e
    if resp is None:
        # Response syntax:
        # {
        #     'thingTypeName': 'string',
        #     'thingTypeId': 'string',
        #     'thingTypeArn': 'string',
        #     'thingTypeProperties': {
        #         'thingTypeDescription': 'string',
        #         'searchableAttributes': [
        #             'string',
        #         ]
        #     },
        #     'thingTypeMetadata': {
        #         'deprecated': True|False,
        #         'deprecationDate': datetime(2015, 1, 1),
        #         'creationDate': datetime(2015, 1, 1)
        #     }
        # }        
        default_thing_type = iot_client.create_thing_type(
            thingTypeName= default_thing_type_name,
            thingTypeProperties= {
                'thingGroupDescription': default_thing_type_description,
            #     'searchableAttributes': [
            #         'string',
            #     ]
            },
            tags=[{"Key":k, "Value":v} for k,v in tags.items()]
        )
    else:
        _top_logger.info(f"Default thing type {default_thing_type_name} creation skipped as it's already available. Info: {resp}")
        return None
    #-------------------------------------
    # define Provisioning Template
    #* WILL BE DEFINED WITH CDK WITH ITS ROLE!

    #-------------------------------------
    #* create bootstrap certificate
    # Response syntax:
    # {
    #     'certificateArn': 'string',
    #     'certificateId': 'string',
    #     'certificatePem': 'string',
    #     'keyPair': {
    #         'PublicKey': 'string',
    #         'PrivateKey': 'string'
    #     }
    # }
    bootstrap_cert_resp = iot_client.create_keys_and_certificate( setAsActive=True )
    # we need to update our trusted store
    # - reade current trusted store content
    try:
        with open(local_trusted_store_path, "r") as f:
            curr_trst = f.readlines()
    except Exception as e:
        _top_logger.warning(f"Was not able to load current trusted store with exception {e}")
        curr_trst = []
    # - add created certificate
    curr_trst.append(bootstrap_cert_resp["certificatePem"])
    # - move current trusted store to backup
    try:
        trst_bckp = local_trusted_store_path.with_stem(f"{local_trusted_store_path.stem}.{uuid4()}")
        local_trusted_store_path.rename(trst_bckp)
    except Exception as e:
        _top_logger.warning(f"Was not able to backup current trusted store with exception {e}")
    # try:
    # except Exception as e:
    #     _top_logger.warning(f"Fail to backup trusted store before the update with exception {e}")
    # - write down updated store 
    with open(local_trusted_store_path, "w") as f:
        f.writelines(curr_trst)
    # we need to store bootstrapping cert and keys
    # create cert folder (if not available) and store the cert data
    try:
        local_bootstrapcert_folder.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _top_logger.warning(f"Was not able create folder for bootstrap certificates with exception {e}")
    cert_uuid = str(uuid4())
    btstrp_cert_path = local_bootstrapcert_folder / f"{cert_uuid}.json"
    with open(btstrp_cert_path, "w") as f:
        json.dump(bootstrap_cert_resp, f, indent=3)
    btstrp_pem_path = local_bootstrapcert_folder / f"{cert_uuid}.cert.pem"
    with open(btstrp_pem_path, "w") as f:
        f.writelines(bootstrap_cert_resp["certificatePem"])
    btstrp_keys_path = local_bootstrapcert_folder / f"{cert_uuid}.keys.pem"
    with open(btstrp_keys_path, "w") as f:
        f.writelines(bootstrap_cert_resp["keyPair"].values())
    # -----------------------------
    #* define the Policy for Bootstrap Certificate
    # Response syntax:
    # {
    #     'policyName': 'string',
    #     'policyArn': 'string',
    #     'policyDocument': 'string',
    #     'policyVersionId': 'string'
    # }
    # @see https://docs.aws.amazon.com/iot/latest/developerguide/example-iot-policies.html
    bootstrap_iot_policy = iot_client.create_policy(
        policyName=bootstrap_policy_name,
        tags=[{"Key":k, "Value":v} for k,v in tags.items()],
        policyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["iot:Connect"],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Publish","iot:Receive"],
                    "Resource": [
                        f"arn:aws:iot:{session.region_name}:{iot_account_id}:topic/$aws/certificates/create/*",
                        f"arn:aws:iot:{session.region_name}:{iot_account_id}:topic/$aws/provisioning-templates/{bootstrap_template_name}/provision/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": "iot:Subscribe",
                    "Resource": [
                        f"arn:aws:iot:{session.region_name}:{iot_account_id}:topicfilter/$aws/certificates/create/*",
                        f"arn:aws:iot:{session.region_name}:{iot_account_id}:topicfilter/$aws/provisioning-templates/{bootstrap_template_name}/provision/*"
                    ]
                }
            ]
        })
    )
    # -------------------------------------------
    # Give the AWS IoT service permission to create or update IoT resources such as things and certificates 
    # in your account when provisioning devices. 
    # Do this by attaching the AWSIoTThingsRegistration managed policy to an IAM role (called the provisioning role) 
    # that trusts the AWS IoT service principal.

    # -------------------------------------------
    # Attach policy to Bootstrap certificate
    # Possible Exceptions
    # IoT.Client.exceptions.ResourceNotFoundException
    # IoT.Client.exceptions.InvalidRequestException
    # IoT.Client.exceptions.ThrottlingException
    # IoT.Client.exceptions.UnauthorizedException
    # IoT.Client.exceptions.ServiceUnavailableException
    # IoT.Client.exceptions.InternalFailureException
    # IoT.Client.exceptions.LimitExceededException
    try:
        iot_client.attach_policy(
            policyName=bootstrap_policy_name,
            target=bootstrap_cert_resp["certificateArn"]
        )
    except Exception as e:
        _top_logger.error(f"Fail to attach bootstrapping policy to bootstrap certificate with exception {e}")


    _top_logger.info(f"Successful pre-deployment bootstrapping!")
    return True

