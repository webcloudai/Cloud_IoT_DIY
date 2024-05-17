'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''

from typing import Dict, Callable, List
# import PySimpleGUI as sg
import json
import sys
from pathlib import Path
from queue import Queue
from dataclasses import dataclass
# from time import sleep
# Setup logging.
import logging
logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig(level=aegis_config['log_level'])
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler())


#--- Proprietary modules
# from mqtt_client.mqtt_ui import MqttLayout
from mqtt_client.mqtt_client import MqttClient, PubSub
#--- we'll add path to PATH to enable import of common_project_config
sys.path.append("../Cloud_IoT_DIY_cloud")
from common_project_config import ProjectConfig


@dataclass
class ThingFleetProvParams:
    ThingName:str
    ThingGroup:str
    ThingType:str
    ThingBuilding:str
    ThingLocation:str
    # MqttUrl:str
    # ApiUrl:str
    def __init__(self, **values) -> None:
        self.ThingName = values.get("ThingName", None)
        self.ThingGroup = values.get("ThingGroup", None)
        self.ThingType = values.get("ThingType", None)
        self.ThingBuilding = values.get("ThingBuilding", None)
        self.ThingLocation = values.get("ThingLocation", None)


class FleetProv():

    def __init__(self, project_config:ProjectConfig, thing_params:ThingFleetProvParams, commQueue:Queue=None) -> None:
        self.pr_config = project_config
        self.t_params = thing_params
        self._logs:List[str] = []
        self.process_failure = None
        self.log_callback:Callable = None
        self.log_queue:Queue = None
        self.comm_queue:Queue = commQueue
        self._init_prov_steps()

        #**********************************
        self.fleet_prov_thing_type = self.pr_config.iot_default_thing_type
        self.fleet_prov_topics = {
            "CERT_REQUEST_TOPIC": {"topic": self.pr_config.iot_prov_topic_certificates, "ops": PubSub.PUB},
            "CERT_REQ_ACCEPTED_TOPIC": {"topic": self.pr_config.iot_prov_topic_certificates_accepted, "ops": PubSub.SUB, "known_process":"fleet_thing_cert"},
            "CERT_REQ_REJECTED_TOPIC": {"topic": self.pr_config.iot_prov_topic_certificates_rejected, "ops": PubSub.SUB},
            "THING_PROV_TOPIC": {"topic": self.pr_config.iot_prov_topic_provision, "ops": PubSub.PUB},
            "THING_PROV_ACCEPTED_TOPIC": {"topic": self.pr_config.iot_prov_topic_provision_accepted, "ops": PubSub.SUB},
            "THING_PROV_REJECTED_TOPIC": {"topic": self.pr_config.iot_prov_topic_provision_rejected, "ops": PubSub.SUB},
        }
        self.mqtt_client = None
        self.mqtt_url = self.pr_config.mqtt_url  #"a2pb2hra83g37i-ats.iot.us-east-1.amazonaws.com"  
        self.trusted_store:Path = Path(self.pr_config.firmware_folder) / self.pr_config.tls_certstore
        self.things_sensitives_folder:Path = Path(self.pr_config.my_things)
        self.thing_cert = self.things_sensitives_folder / f"{self.t_params.ThingName}.cert.pem"
        self.thing_key = self.things_sensitives_folder / f"{self.t_params.ThingName}.keys.pem"
        # ----- Create communication queue
        self.messaging_queue = Queue()

    def _init_prov_steps(self):
        self.fleet_prov_steps = {
            "CONNECT": True,
            "SUB_CERT": True,
            "PUB_CERT": True,
            "SUB_THINGPROV": True,
            "PUB_THINGPROV": True,
            "DISCONNECT": True
        }

    def process_completed(self)->bool:
        if self.process_failure:
            return True
        for k,v in self.fleet_prov_steps.items():
            if v:
                _top_logger.debug(f"Step {k} was not completed")
                return False
        return True

    def logs_append(self, message:str):
        self._logs.append(message)
        if isinstance(self.log_callback, Callable):
            self.log_callback()
            return
        if isinstance(self.log_queue, Queue):
            self.log_queue.put_nowait("\n".join(self._logs))

    def _fleet_prov_mqtt_client(self)->MqttClient:
        ''' '''
        #################################################################################
        # Init MQTT client
        #
        # ----- Instantiate client (MQTT MTLS will be configured but client not connected)
        # find latest bootstrap cert (the LATEST bootstrap cert/keys will be used by default)
        newest_cert_p:Path = sorted([v for v in Path(self.pr_config.bootstrapcert_local_folder).glob("*.cert.pem")], key=lambda x: x.stat().st_mtime)[-1]
        newest_keys_p:Path = newest_cert_p.with_stem(newest_cert_p.stem.replace(".cert",".keys"))
        # init client
        self.mqtt_client = MqttClient(
            mqtt_uri=self.mqtt_url,
            messaging_queue=self.messaging_queue,
            trusted_store=self.trusted_store,
            bootstrap_cert=newest_cert_p, # Path("../_MyThings/bootstrap_certificates/5ee6e49d-dbd7-40ae-a38a-5a12cb88ccca.cert.pem"),
            bootstrap_key=newest_keys_p,  # Path("../_MyThings/bootstrap_certificates/5ee6e49d-dbd7-40ae-a38a-5a12cb88ccca.keys.pem"),
            thing_cert=self.thing_cert,
            thing_key=self.thing_key,
            thing_uuid=self.t_params.ThingName,
            topics=list(self.fleet_prov_topics.values())
        )
        return self.mqtt_client

    def _handle_queue_message(self):
        ''' '''
        have_messages = True
        while have_messages:
            try:  
                # Check messages in queue
                event_message = self.messaging_queue.get(block=True, timeout=2) # .get_nowait()
                _top_logger.debug(f"\n{json.dumps(event_message, indent=2)}")
            except Exception as e:
                # no messages available after 3 sec - we have a problem
                # _top_logger.error(f"FAIL to collect any response on CERT_REQUEST_TOPIC message")
                have_messages = False
                _top_logger.debug(f"---no message---")
            else:
                if event_message["scope"].lower() == "connect_prov" or event_message["scope"].lower() == "disconnect_prov":
                    self.logs_append(f"Connect response:\n{json.dumps(event_message, indent=3)}")
                    # If connection was not successful - we have an issue
                    if "success" not in event_message.get("code","fail").lower():
                        self.process_failure = True
                elif event_message["scope"].lower().startswith("subscribe"):
                    self.logs_append(f"Subscribe response:\n{json.dumps(event_message, indent=3)}")
                    if not event_message.get("code","fail").lower().startswith("subscribed"):
                        self.process_failure = True
                elif event_message["scope"].lower() == "unsubscribe":
                    self.logs_append(f"Unsubscribe response:\n{json.dumps(event_message, indent=3)}")
                elif event_message["scope"].lower().startswith("send"):
                    self.logs_append(f"Message sent:\n{json.dumps(event_message, indent=3)}")
                elif event_message["scope"].lower().startswith("message"):
                    self.logs_append(f"Message received:\n{json.dumps(event_message, indent=3)}")
                    # If message received from */rejected topic - we have an issue
                    if "/rejected" in event_message["scope"]:
                        self.process_failure = True
                # elif event_message["scope"].lower() == "?":
                #     pass
                else:
                    self.logs_append(f"MQTT client message:\n{json.dumps(event_message, indent=3)}")
        return

    def disconnect(self):
        if not self.fleet_prov_steps["CONNECT"]:
            self.logs_append(f"Disconnect from host...")
            self.mqtt_client.disconnect()
            self._handle_queue_message()


    def provision(self):
        ''' '''
        if self.mqtt_client is None:
            self._fleet_prov_mqtt_client()
        # 1. Start MQTT connection with host using claim certificate
        # NOTE that it's extremely important to provide name for the client!
        if self.fleet_prov_steps["CONNECT"]:
            self.logs_append(f"Connect to host...")
            self.mqtt_client.connect()
            self._handle_queue_message()
            self.fleet_prov_steps["CONNECT"] = False
            if self.process_failure:
                self.disconnect()
                if self.comm_queue:
                    self.comm_queue.put_nowait("FAIL")
                return

        # 2. Subscribe to two topics CERT_REQ_ACCEPTED_TOPIC and CERT_REQ_REJECTED_TOPIC
        if self.fleet_prov_steps["SUB_CERT"]:
            self.logs_append(f"Subscribe to two topics...")
            self.mqtt_client.sub( topics=
                [
                    self.fleet_prov_topics["CERT_REQ_ACCEPTED_TOPIC"]["topic"],
                    self.fleet_prov_topics["CERT_REQ_REJECTED_TOPIC"]["topic"] 
                ]
            )
            self._handle_queue_message()
            self.fleet_prov_steps["SUB_CERT"] = False
            if self.process_failure:
                self.disconnect()
                if self.comm_queue:
                    self.comm_queue.put_nowait("FAIL")
                return

        # 3. Publish empty message to topic CERT_REQUEST_TOPIC
        if self.fleet_prov_steps["PUB_CERT"]:
            self.logs_append(f"Publish to topic...")
            self.mqtt_client.pub(self.fleet_prov_topics["CERT_REQUEST_TOPIC"]["topic"],None)
            self._handle_queue_message()

            # Collect parameters from message in CERT_REQ_ACCEPTED_TOPIC
            # thing cert and keys will be stored locally as we provided Client with "known_process":"fleet_thing_cert"

            self.logs_append(f"Unsubscribe from two topics...")
            self.mqtt_client.unsub( topics=[
                self.fleet_prov_topics["CERT_REQ_ACCEPTED_TOPIC"]["topic"],
                self.fleet_prov_topics["CERT_REQ_REJECTED_TOPIC"]["topic"] ] )
            self._handle_queue_message()
            self.fleet_prov_steps["PUB_CERT"] = False
            if self.process_failure:
                self.disconnect()
                if self.comm_queue:
                    self.comm_queue.put_nowait("FAIL")
                return
        

        # 4. Subscribe to two topics THING_PROV_ACCEPTED_TOPIC and THING_PROV_REJECTED_TOPIC
        if self.fleet_prov_steps["SUB_THINGPROV"]:
            self.logs_append(f"Subscribe to two topics...")
            self.mqtt_client.sub( topics=
                [
                    self.fleet_prov_topics["THING_PROV_ACCEPTED_TOPIC"]["topic"],
                    self.fleet_prov_topics["THING_PROV_REJECTED_TOPIC"]["topic"] 
                ]
            )
            self._handle_queue_message()
            self.fleet_prov_steps["SUB_THINGPROV"] = False
            if self.process_failure:
                self.disconnect()
                if self.comm_queue:
                    self.comm_queue.put_nowait("FAIL")
                return

        # 5. Publish 'provisioning request' to topic THING_PROV_TOPIC
        if self.fleet_prov_steps["PUB_THINGPROV"]:
            self.logs_append(f"Publish to provisioning topic...")
            self.mqtt_client.pub(self.fleet_prov_topics["THING_PROV_TOPIC"]["topic"], self.prov_message())
            self._handle_queue_message()

            self.logs_append(f"Unsubscribe from two topics...")
            self.mqtt_client.unsub( topics=[
                self.fleet_prov_topics["THING_PROV_ACCEPTED_TOPIC"]["topic"],
                self.fleet_prov_topics["THING_PROV_REJECTED_TOPIC"]["topic"] ] )
            self._handle_queue_message()
            self.fleet_prov_steps["PUB_THINGPROV"] = False
            if self.process_failure:
                self.disconnect()
                if self.comm_queue:
                    self.comm_queue.put_nowait("FAIL")
                return

        # If provisioning successful - disconnect and return TRUE
        #  saving device certificate and key is caller responsibility (not always needed)
        if self.fleet_prov_steps["DISCONNECT"]:
            self.logs_append(f"Disconnect from host...")
            self.disconnect()
            self.fleet_prov_steps["DISCONNECT"] = False

        if self.comm_queue:
            self.comm_queue.put_nowait("SUCCESS")


    #####################################################################
    # THING PROV specific code
    def prov_message(self)->str:
        return json.dumps(
            {
                "certificateOwnershipToken": MqttClient.cert_req_response["certificateOwnershipToken"] if MqttClient.cert_req_response else ">>>certificateOwnershipToken collected",
                "parameters": {
                    "appName": self.pr_config.mqtt_app_name,
                    "thingName": self.t_params.ThingName,
                    "thingSerial": "SOME MAC ADDRESS",
                    "thingGroup": self.pr_config.things_group_name,
                    "thingType": self.pr_config.iot_default_thing_type,
                    "buildingId": self.t_params.ThingBuilding,
                    "locationId": self.t_params.ThingLocation
                }
            }
            # , indent=3
        )
