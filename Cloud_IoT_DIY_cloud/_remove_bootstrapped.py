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

import boto3

def _remove_bootstrapped(
        *, 
        session:boto3.Session,
        default_group_name:str,
        local_trusted_store_path:Path,
        local_bootstrapcert_folder:Path,
        bootstrap_policy_name:str,
    ):
    ''' this will REMOVE 
    - default thing group
    - bootstrap certificate (trusted store to be updated and cert data stored locally)
    - iot policy for bootstrap certificate
    and detach policy from bootstrap certificate 
    '''

    iot_client = session.client("iot")
    #-------------------------------------
    #* remove default IoT Group
    # collect group info
    # Response Syntax:
    '''
        {
            'thingGroupName': 'string',
            'thingGroupId': 'string',
            'thingGroupArn': 'string',
            'version': 123,
            'thingGroupProperties': {
                'thingGroupDescription': 'string',
                'attributePayload': {
                    'attributes': {
                        'string': 'string'
                    },
                    'merge': True|False
                }
            },
            'thingGroupMetadata': {
                'parentGroupName': 'string',
                'rootToParentThingGroups': [
                    {
                        'groupName': 'string',
                        'groupArn': 'string'
                    },
                ],
                'creationDate': datetime(2015, 1, 1)
            },
            'indexName': 'string',
            'queryString': 'string',
            'queryVersion': 'string',
            'status': 'ACTIVE'|'BUILDING'|'REBUILDING'
        }
    '''    
    try:
        resp = iot_client.describe_thing_group( thingGroupName=default_group_name )
        resp = None if isinstance(resp, dict) and resp.get("thingGroupName","").lower()!=default_group_name.lower() else resp
    except iot_client.exceptions.ResourceNotFoundException:
        _top_logger.info(f"No IoT Group name '{default_group_name}' found to destroy")
        resp = None
    except Exception as e:
        _top_logger.error(f"Fail to collect IoT group '{default_group_name}' with exception {e}")
        raise e
    if isinstance(resp, dict):
        try:
            iot_client.delete_thing_group(
                thingGroupName=default_group_name,
                expectedVersion=resp["version"]
            )
        except Exception as e:
            _top_logger.error(f"Fail to delete thing group '{default_group_name}' with exception {e}")
    else:
        _top_logger.info(f"Fail to collect IoT group '{default_group_name}'")

    #------------------------------
    # Certificate cleanup
    #* Collect Policy (will be used to identify certificate to delete)
    # Response Syntax
    '''
        {
            'policyName': 'string',
            'policyArn': 'string',
            'policyDocument': 'string',
            'defaultVersionId': 'string',
            'creationDate': datetime(2015, 1, 1),
            'lastModifiedDate': datetime(2015, 1, 1),
            'generationId': 'string'
        }
    '''
    policy_targets = {}
    try:
        # bootstrap_iot_policy_versions = iot_client.list_policy_versions( policyName=bootstrap_policy_name )
        # bootstrap_iot_policy = iot_client.get_policy( policyName=bootstrap_policy_name )
        policy_targets = iot_client.list_targets_for_policy(policyName=bootstrap_policy_name)
    except Exception as e:
        _top_logger.error(f"Fail to collect Policy '{bootstrap_policy_name}' will proceed with deleting oldest bootstrap cert")
    
    #* Find the certificate to remove
    certs = sorted([v for v in local_bootstrapcert_folder.glob("*.json")], key=lambda x: x.stat().st_mtime)
    cert_targets = policy_targets.get("targets", []) if isinstance(policy_targets, dict) else []
    cert_2_delete:Path = None # type: ignore
    if len(cert_targets)>0:
        for c in certs:
            try:
                with open(c, "r") as f:
                    cert_data = json.load(f)
                if cert_data["certificateArn"] in cert_targets:
                    cert_2_delete = c
                    break
            except Exception as e:
                _top_logger.warning(f"Fail to check cert {c} with exception {e}")
    if cert_2_delete is None:
        if len(certs)>0:
            #* Remove oldest created Cert
            cert_2_delete:Path = certs[0]
            _top_logger.warning(f"Was not able to find correct cert. Will delete the oldest one {cert_2_delete}")
        else:
            _top_logger.warning(f"No bootstrap cert found")
            cert_2_delete = None # type: ignore
    else:
        _top_logger.info(f"Found attached cert - {cert_2_delete}")
    if cert_2_delete:
        # We need to find correct certificate first
        with open(cert_2_delete, "r") as f:
            cert_data = json.load(f)
        # To delete a certificate, first use the DetachPolicy action to detach all policies. 
        # Next, use the UpdateCertificate action to set the certificate to the INACTIVE status.
        # step 1
        try:
            response = iot_client.detach_policy(
                policyName=bootstrap_policy_name,
                target=cert_data["certificateArn"]
            )
        except Exception as e:
            _top_logger.error(f"Fail to detach policy {bootstrap_policy_name} from certificate with exception {e}")

        # step 2
        # 
        try:
            cert_deactivate_response = iot_client.update_certificate(
                certificateId=cert_data["certificateId"],
                newStatus='INACTIVE'
            )
        except Exception as e:
            _top_logger.error(f"Fail to deactivate certificate with exception {e}")
        # step 3
        try:
            cert_delete_response = iot_client.delete_certificate(
                certificateId=cert_data["certificateId"],
                forceDelete=True
            )
        except Exception as e:
            _top_logger.error(f"Fail to delete certificate with exception {e}")
        # step 4
        # delete cert from local folder
        try:
            cert_2_delete.unlink()
        except Exception as e:
            _top_logger.error(f"Fail to remove local certificate at path {cert_2_delete} with exception {e}")
        # step 5
        # remove cert from the trusted store
        try:
            with open(local_trusted_store_path, "r") as f:
                curr_trst = f.readlines()
        except Exception as e:
            _top_logger.warning(f"Was not able to load current trusted store with exception {e}")
            curr_trst = []
        try:
            updated_trst = []
            i = 0
            cert_d = []
            cert_pem = cert_data["certificatePem"].split("\n")
            for line in curr_trst:
                if line.startswith(cert_pem[i]):
                    # we have certificate start
                    cert_d = [line]
                    i += 1
                    if i == len(cert_pem):
                        # that was exactly our cert and we've just removed it
                        _top_logger.info(f"Found and removed cert from the trusted store")
                        cert_d = []
                        i = 0
                    continue
                elif len(cert_d)>0:
                    # we have cert in progress but not of our interest
                    updated_trst.extend(cert_d)
                    cert_d = []
                    i = 0
                    continue
                else:
                    updated_trst.append(line)
                    i+=1
        except Exception as e:
            _top_logger.warning(f"Was not able to update trusted store with exception {e}")
            curr_trst = []
        # - write down updated store 
        with open(local_trusted_store_path, "w") as f:
            f.writelines(updated_trst)

        # Step 6. Remove successful upload marker
        upload_marker = cert_2_delete.with_stem("upload_completed").with_suffix("txt")
        try:
            upload_marker.unlink()
        except Exception as e:
            _top_logger.error(f"Fail to remove upload marker at path {upload_marker} with exception {e}")
        

    #------------------------------
    # remove policy
    try:
        rem_policy_resp = iot_client.delete_policy(policyName=bootstrap_policy_name)
    except Exception as e:
        _top_logger.error(f"Fail to delete bootstrap policy {bootstrap_policy_name} with exception {e}")

    #------------------------------
    #! remove log groups (IoT log group blocks redeployments)




    _top_logger.info(f"Successful post-destroy cleanup!")
    return True
