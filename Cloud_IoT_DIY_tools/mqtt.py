'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
# from __future__ import annotations
from typing import Dict, Callable
import PySimpleGUI as sg
import json
import sys
from pathlib import Path
from queue import Queue
from jinja2.nativetypes import NativeEnvironment
# Setup logging.
import logging
logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig(level=aegis_config['log_level'])
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler())


#--- Proprietary modules
from mqtt_client.mqtt_ui import MqttLayout
from mqtt_client.mqtt_client import MqttClient, PubSub
#--- we'll add path to PATH to enable import of common_project_config
sys.path.append("../Cloud_IoT_DIY_cloud")
from common_project_config import ProjectConfig

##############################################################
# General Principle
#
# Step enum defines names for every step and substeps
# Child of ProcessNavigator defines what steps are required and in what order
# Child of StepController defines what each step is doing
#
# ProcessNavigator:
# - returns tab group - list of tabs (steps) required to complete the Process
# - handle cloud connection for all tabs (if needed)
# - aggregate delegates from underlying StepControllers
#
# StepController returns it's tab only! 
# But also in charge of delegates - dict with {event name: callable} to handle events
# 
#
# Scenario 1 (simple):
# Each StepController defines ONE action
#
# Scenario 2 (complicated):
# Step consists of substeps - in this case
# - Step has property _subprocess defined as another Child of ProcessNavigator
# - no definition of tab required - it'll be handled by base StepController with the help of ProcessNavigator

def prov_message()->str:
    return json.dumps(
        {
            "certificateOwnershipToken": MqttClient.cert_req_response["certificateOwnershipToken"] if MqttClient.cert_req_response else ">>>certificateOwnershipToken collected",
            "parameters": {
                "appName": pr_config.mqtt_app_name,
                "thingName": thing_name,
                "thingSerial": "SOME MAC ADDRESS",
                "thingGroup": pr_config.things_group_name,
                "thingType": thing_type,
                "buildingId": building_id,
                "locationId": location_id
            }
        }
        # , indent=3
    )

if __name__=="__main__":

    
    #################################################################################
    # Collect Project Configuration
    #
    pr_config = ProjectConfig.create_from_file() #jinja_sections=["aws_iot_provisioning", "auth", "mqtt_topic"])
    # we need to render the rest of the topics with regards to all known variables
    #**********************************
    #! HARDCODED PART of CONFIG !
    #* This values will be REQUESTED during real device provisioning
    building_id = "b001"
    location_id = "r003"
    thing_name = "device003"
    #**********************************
    thing_type = pr_config.iot_default_thing_type
    jjenv = NativeEnvironment()
    telemetry_topic = jjenv.from_string(pr_config.telemetry_topic).render(
            **{
                **pr_config.config_data,
                **{
                    "building_id": building_id,
                    "location_id": location_id,
                    "thing_type": thing_type,
                    "thing_name": thing_name
                }
            })
    status_topic = jjenv.from_string(pr_config.status_topic).render(
            **{
                **pr_config.config_data,
                **{
                    "building_id": building_id,
                    "location_id": location_id,
                    "thing_type": thing_type,
                    "thing_name": thing_name
                }
            })
    control_topic = jjenv.from_string(pr_config.control_topic).render(
            **{
                **pr_config.config_data,
                **{
                    "building_id": building_id,
                    "location_id": location_id,
                    "thing_type": thing_type,
                    "thing_name": thing_name
                }
            })
    mqtt_url = pr_config.mqtt_url  #"a2pb2hra83g37i-ats.iot.us-east-1.amazonaws.com"  
    trusted_store:Path = Path(pr_config.firmware_folder) / pr_config.tls_certstore
    things_sensitives_folder:Path = Path(pr_config.my_things)
    thing_cert=things_sensitives_folder / f"{thing_name}.cert.pem"
    thing_key=things_sensitives_folder / f"{thing_name}.keys.pem"

    #################################################################################
    # Init MQTT client
    #
    # ----- Create communication queue
    messaging_queue = Queue()
    # ----- Instantiate client (MQTT MTLS will be configured but client not connected)
    # find latest bootstrap cert (the LATEST bootstrap cert/keys will be used by default)
    newest_cert_p:Path = sorted([v for v in Path(pr_config.bootstrapcert_local_folder).glob("*.cert.pem")], key=lambda x: x.stat().st_mtime)[-1]
    newest_keys_p:Path = newest_cert_p.with_stem(newest_cert_p.stem.replace(".cert",".keys"))
    # init client
    mqtt_client = MqttClient(
        mqtt_uri=mqtt_url,
        messaging_queue=messaging_queue,
        trusted_store=trusted_store,
        bootstrap_cert=newest_cert_p, # Path("../_MyThings/bootstrap_certificates/5ee6e49d-dbd7-40ae-a38a-5a12cb88ccca.cert.pem"),
        bootstrap_key=newest_keys_p,  # Path("../_MyThings/bootstrap_certificates/5ee6e49d-dbd7-40ae-a38a-5a12cb88ccca.keys.pem"),
        thing_cert=thing_cert,
        thing_key=thing_key,
        thing_uuid=thing_name,
        topics=[
            {"topic": pr_config.iot_prov_topic_certificates, "ops": PubSub.PUB},
            {"topic": pr_config.iot_prov_topic_certificates_accepted, "ops": PubSub.SUB, "known_process":"fleet_thing_cert"},
            {"topic": pr_config.iot_prov_topic_certificates_rejected, "ops": PubSub.SUB},
            {"topic": pr_config.iot_prov_topic_provision, "ops": PubSub.PUB},
            {"topic": pr_config.iot_prov_topic_provision_accepted, "ops": PubSub.SUB},
            {"topic": pr_config.iot_prov_topic_provision_rejected, "ops": PubSub.SUB},
            {"topic": telemetry_topic, "ops": PubSub.PUB},
            {"topic": status_topic, "ops": PubSub.PUB},
            {"topic": control_topic, "ops": PubSub.SUB}
        ]
    )
    #################################################################################
    # Configure UI
    #
    mqtt_prov_process_components = [
        [
            (pr_config.iot_prov_topic_certificates_accepted, None),     # None for SUB only topics!
            (pr_config.iot_prov_topic_certificates, ''),
            (pr_config.iot_prov_topic_provision_rejected, None)         # None for SUB only topics!
        ],
        [
            (pr_config.iot_prov_topic_certificates_rejected, None),     # None for SUB only topics!
            (pr_config.iot_prov_topic_provision_accepted, None),        # None for SUB only topics!
            (pr_config.iot_prov_topic_provision, prov_message())
        ]
    ]
    mqtt_work_process_components = [
        [
            (telemetry_topic, '{"foo": 1}'),
            (control_topic, None)
        ],
        [
            (status_topic, '{"bar": 100}')
        ]
    ]
    mqtt_layout = MqttLayout(
        mqtt_host=mqtt_url,
        layout_title=f"CHANGE IN CODE WHEN NEEDED! building_id: '{building_id}' | location_id: '{location_id}'  |  thing_type: '{thing_type}'  |  thing_name: '{thing_name}'",
        mqtt_channels_prov=mqtt_prov_process_components,
        mqtt_channels_work=mqtt_work_process_components
    )

    main_window = sg.Window("Test MQTT and AWS IoT Core Provisioning", mqtt_layout.layout, finalize=True)
    current_window = main_window

    while True:

        # Check messages in queue
        try:  
            event_message = messaging_queue.get_nowait()
        except Exception as e:
            # no messages available
            pass
        else: 
            # got message
            if event_message["scope"].lower() == "connect_prov" or event_message["scope"].lower() == "disconnect_prov":
                if event_message["scope"].lower() == "disconnect_prov":
                    current_window["connect_prov"].update(disabled=False)
                    current_window["disconnect_prov"].update(disabled=True)
                else:
                    current_window["connect_prov"].update(disabled=True)
                    current_window["disconnect_prov"].update(disabled=False)
                current_window[mqtt_layout.prov_connect_incoming].update(json.dumps(event_message), append=True, autoscroll=True)
            elif event_message["scope"].lower() == "connect_work" or event_message["scope"].lower() == "disconnect_work":
                if event_message["scope"].lower() == "disconnect_work":
                    current_window["connect_work"].update(disabled=False)
                    current_window["disconnect_work"].update(disabled=True)
                else:
                    current_window["connect_work"].update(disabled=True)
                    current_window["disconnect_work"].update(disabled=False)
                current_window[mqtt_layout.work_connect_incoming].update(json.dumps(event_message), append=True, autoscroll=True)
            elif event_message["scope"].lower().startswith("subscribe"):
                current_window[event_message["scope"].replace("Subscribe","Incoming")].update(json.dumps(event_message), append=True, autoscroll=True)
            elif event_message["scope"].lower() == "unsubscribe":
                pass
            elif event_message["scope"].lower().startswith("send"):
                current_window[event_message["scope"].replace("Send","Incoming")].update(json.dumps(event_message), append=True, autoscroll=True)
            elif event_message["scope"].lower().startswith("message"):
                current_window[event_message["scope"].replace("Message","Incoming")].update(json.dumps(event_message), append=True, autoscroll=True)
                if isinstance(event_message, dict) and "action" in event_message:
                    if event_message["action"] == "Update|Payload|iot_prov_topic_provision":
                        current_window[f"Payload|{pr_config.iot_prov_topic_provision}"].update(json.dumps(prov_message()), append=False)
            elif event_message["scope"].lower() == "?":
                pass
            current_window.Refresh()


        # Check events from all windows
        event_window, event, values = sg.read_all_windows(timeout=10)
        if event==sg.TIMEOUT_EVENT:
            # that's Ok -  no events found
            # we just need non-blocking method
            continue
        _top_logger.debug(f"\nevent: {event}\nvalues:\n{json.dumps(values, indent=3)}")

        if isinstance(event, str):
            event_type = event.split("|")[0]
            event_source = event.split("|")[-1]
            if event_type.lower().strip().startswith("connect"):
                mqtt_client.connect(cert_type=("bootstrapping" if event_type.lower().strip()=="connect_prov" else "device"))
            elif event_type.lower().strip().startswith("disconnect"):
                mqtt_client.disconnect()
            elif event_type.lower().strip() =="subscribe":
                # we have a subscribe request
                # event is ALWAYS of format 'Subscribe|<topic>
                mqtt_client.sub(topics=[event_source])
            elif event_type.lower().strip() == "unsubscribe":
                # we have a subscribe request
                mqtt_client.unsub(topics=[event_source])
            elif event_type.lower().strip() == "send":
                # we have a send message request
                message=values[f"Payload|{event_source}"]
                message = None if message=="N/A" else message
                try:
                    message = json.loads(message)
                    message = message if isinstance(message, str) else json.dumps(message)
                except Exception as ee:
                    pass
                mqtt_client.pub(topic=event_source, message=message)
        # 3.1. Always check if main window closed first
        if current_window==main_window and event == sg.WIN_CLOSED:           # always,  always give a way out!
            break

    # Clean up
    try:
        mqtt_client.disconnect()
    except Exception as e:
        _top_logger.error(f"Fail to disconnect the client with exception {e}")
    main_window.close()
