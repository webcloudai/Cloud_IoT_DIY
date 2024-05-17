'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable, Union
from enum import Enum
from pathlib import Path
from queue import Queue
import paho.mqtt.client as mqtt_client
import paho.mqtt.properties as mqtt_props
import ssl
import json
import logging
from dataclasses import dataclass

_top_logger = logging.getLogger(__name__)

class PubSub(Enum):
    PUB = "Publish"
    SUB = "Subscribe"
    PUBSUB = "Publish&Subscribe"

@dataclass
class TopicConfig:
    ''' '''
    topic:str
    ops:PubSub
    on_message:Callable=None
    known_process:str=None
    # on_publish:Callable=None


class MqttClient:
    ''' 
    This is actually a singleton class. Second init will raise an exception!
    TODO: refactor to real singleton
    '''
    # the only instance
    the_only_instance:MqttClient=None
    # thing new cert response
    cert_req_response:Dict[str,str]=None
    # Queue to communicate with UI
    feedbackQueue:Queue = None
    # Current client certificate used for connection
    current_cert_type:str = "bootstrapping"
    # dict of message ids used to identify source of callback
    mid:Dict[int,str] = {} 
    # dict of topics
    topics:Dict[str,TopicConfig] = {}

    @staticmethod
    def on_connect(client, user_data, flags, rc, m_props:mqtt_props.Properties=None):
        ''' 
            will be used two times potentially
            first time to connect/disconnect with bootstrapping cert
            second time to connect/disconnect with device cert
        '''
        _top_logger.info(f"Connection code {rc}")
        props = m_props or {}
        MqttClient.feedbackQueue.put_nowait({ 
            "scope":"CONNECT_PROV" if MqttClient.current_cert_type=="bootstrapping" else "CONNECT_WORK", 
            "code":str(rc).upper(),
            # "data": { k:getattr(props, k,None) for k in getattr(props, "names",{}).keys() }
            "data": props.json() if isinstance(props, mqtt_props.Properties) else None
        })

    @staticmethod
    def on_connect_fail(client=None, user_data=None, flags=None, rc=None, m_props:mqtt_props.Properties=None):
        ''' 
            will be used two times potentially
            first time to connect/disconnect with bootstrapping cert
            second time to connect/disconnect with device cert
        '''
        _top_logger.info(f"Connection code {rc}")
        props = m_props or {}
        MqttClient.feedbackQueue.put_nowait({ 
            "scope":"CONNECT_PROV" if MqttClient.current_cert_type=="bootstrapping" else "CONNECT_WORK", 
            "code":str(rc).upper(),
            # "data": {  k:getattr(props, k,None) for k in getattr(props, "names",{}).keys() }
            "data": props.json() if isinstance(props, mqtt_props.Properties) else None
        })

    @staticmethod
    def on_disconnect(client, user_data, flags, rc, m_props:mqtt_props.Properties=None):
        ''' 
            will be used two times potentially
            first time to connect/disconnect with bootstrapping cert
            second time to connect/disconnect with device cert
        '''
        _top_logger.info(f"Disconnection code {rc}")
        props = m_props or {}
        MqttClient.feedbackQueue.put_nowait({ 
            "scope":"DISCONNECT_PROV" if MqttClient.current_cert_type=="bootstrapping" else "DISCONNECT_WORK", 
            "code":str(rc).upper(),
            # "data": { k:getattr(props, k,None) for k in getattr(props, "names",{}).keys() }
            "data": props.json() if isinstance(props, mqtt_props.Properties) else None
        })

    @staticmethod
    def on_subscribe(client, user_data, mid, rc, m_props:mqtt_props.Properties=None):
        ''' '''
        try:
            message = f'''Subscribed with codes: "{'|'.join([v.getName() for v in rc])}"'''
        except Exception as e:
            message = f"Fail to collect on_subscribe response code with exception {e}"
        _top_logger.info(message)
        props = m_props or {}
        if mid in MqttClient.mid:
            MqttClient.feedbackQueue.put_nowait({ 
                "scope":f"{MqttClient.mid[mid]}", 
                "code":message,
                "data": props.json() if isinstance(props, mqtt_props.Properties) else None
            })

    @staticmethod
    def on_unsubscribe(client, user_data, flags, rc, m_props:mqtt_props.Properties=None):
        ''' '''
        _top_logger.info(f"Unsubscribed with code {rc}")
        props = m_props or {}
        MqttClient.feedbackQueue.put_nowait({ 
            "scope":"UNSUBSCRIBE", 
            "code":str(rc).upper(),
            "data": props.json() if isinstance(props, mqtt_props.Properties) else None
        })

    @staticmethod
    def on_message(client, userdata, message):
        ''' 
        Called when a message has been received on a topic that the client subscribes to 
            and the message does not match an existing topic filter callback. 
        Use message_callback_add() to define a callback that will be called for specific topic filters. 
        on_message will serve as fallback when none matched.
        '''
        try:
            decoded_payload = message.payload.decode("utf-8")
            log_msg = f"Received message {decoded_payload} on topic {message.topic} with QoS {message.qos}"
        except Exception as e:
            log_msg = f"Fail to parse message {message} with exception {e}"
        _top_logger.info(log_msg)
        msg_extend = {}
        # some operations specific for some topics ONLY
        if message.topic in MqttClient.the_only_instance.topics:
            topic_conf:TopicConfig = MqttClient.the_only_instance.topics[message.topic]
            if topic_conf.known_process=="fleet_thing_cert":
                # Known process here is to save created certificatePem, privateKey and store certificateOwnershipToken, certificateId
                try:
                    MqttClient.cert_req_response = json.loads(decoded_payload)
                    # save cert
                    with open(MqttClient.the_only_instance.thing_cert_path, "w") as f:
                        f.write(MqttClient.cert_req_response["certificatePem"])
                    # save key
                    with open(MqttClient.the_only_instance.thing_key_path, "w") as f:
                        f.write(MqttClient.cert_req_response["privateKey"])
                    msg_extend = {
                        "action": "Update|Payload|iot_prov_topic_provision"
                    }
                except Exception as e:
                    log_msg += f"\nFAIL to handle payload object with exception {e}"
        MqttClient.feedbackQueue.put_nowait({ 
            **{
                "scope":f"Message|{message.topic}", 
                "code":"",
                "data": log_msg
            },
            **msg_extend
        })

    @staticmethod
    def on_some_message(*args, **kwargs):
        ''' '''
        _top_logger.info(f"Unsubscribed with code rc")
        # props = m_props or {}
        # MqttClient.feedbackQueue.put_nowait({ 
        #     "scope":"MESSAGE", 
        #     "code":str(rc).upper(),
        #     "data": props.json() if isinstance(props, mqtt_props.Properties) else None
        # })

    @staticmethod
    def on_publish(client, userdata, mid, m_props:mqtt_props.Properties=None):
        ''' 
            Called when a message that was to be sent using the publish() call has completed transmission to the broker. 
            For messages with QoS levels 1 and 2, this means that the appropriate handshakes have completed. 
            For QoS 0, this simply means that the message has left the client. 
            The mid variable matches the mid variable returned from the corresponding publish() call, 
                to allow outgoing messages to be tracked.
            This callback is important because even if the publish() call returns success, 
                it does not always mean that the message has been sent.        '''
        _top_logger.info(f"Published with mid {mid}")
        props = m_props or {}
        if mid in MqttClient.mid:
            MqttClient.feedbackQueue.put_nowait({ 
                "scope":f"{MqttClient.mid[mid]}", 
                "code":"on_publish invoked",
                "data": props.json() if isinstance(props, mqtt_props.Properties) else None
            })

    @staticmethod
    def on_log(*args, **kwargs):
        ''' '''
        _top_logger.info(f"Log with data {args}")
        # props = m_props or {}
        # MqttClient.feedbackQueue.put_nowait({ 
        #     "scope":"MESSAGE", 
        #     "code":str(rc).upper(),
        #     "data": props.json() if isinstance(props, mqtt_props.Properties) else None
        # })


    def __init__(self,
        messaging_queue:Queue,
        mqtt_uri:str="a2pb2hra83g37i-ats.iot.us-east-1.amazonaws.com",
        trusted_store:Path = None,
        bootstrap_cert:Path = None,
        bootstrap_key:Path = None,
        thing_cert:Path = None,
        thing_key:Path = None,
        thing_uuid:str = None,

        topics:List[Union[dict,TopicConfig]] = []
        # callbacks:Dict[str, Callable]=None
    
    ) -> None:
        if MqttClient.the_only_instance:
            raise RuntimeError(f"An attempt to create a second instance of MqttClient singleton class")
        MqttClient.the_only_instance = self
        MqttClient.feedbackQueue = messaging_queue
        self.topics:Dict[str,TopicConfig] = {k.topic:k for k in [ v if isinstance(v, TopicConfig) else TopicConfig(**v) for v in topics]}
        self.uri = mqtt_uri
        self.thing_id = thing_uuid
        self.trusted_store = trusted_store
        self.bootstrap_cert = bootstrap_cert
        self.bootstrap_key = bootstrap_key
        self.client_id = self.thing_id
        self.thing_cert_path:Path = thing_cert
        self.thing_key_path:Path = thing_key
        self.client:mqtt_client.Client = None
        # self.new_client(my_cert_path=self.bootstrap_cert, my_key_path=self.bootstrap_key) # will be called on Connect !

    def new_client(self, *, my_cert_path:Path, my_key_path:Path):
        self.client = mqtt_client.Client(
            client_id=self.client_id,   #! This is extremely important! Without client_id AWS doesn't send a cert back!!! https://www.repost.aws/questions/QU09EItn9DQYKaw_E5Pqb6hA/aws-io-t-fleet-provisioning-doesnt-publish-certificate-response
            protocol=mqtt_client.MQTTv5)
        self.client.tls_set(
            ca_certs=str(self.trusted_store.absolute()),
            certfile=str(my_cert_path.absolute()),
            keyfile=str(my_key_path.absolute()),
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2,
            ciphers=None,
            keyfile_password=""
        )
        self.client.enable_logger() #logger=_top_logger)
        self.client.on_connect = MqttClient.on_connect
        self.client.on_connect_fail = MqttClient.on_connect_fail
        self.client.on_disconnect = MqttClient.on_disconnect
        self.client.on_subscribe = MqttClient.on_subscribe
        self.client.on_unsubscribe = MqttClient.on_unsubscribe
        self.client.on_message = MqttClient.on_message
        self.client.on_publish = MqttClient.on_publish
        self.client.on_log = MqttClient.on_log


    def connect(self, cert_type:str="bootstrapping", ping_in_sec:int=60):
        ''' 
        Only async (you'll need to start a loop with loop_start())
        Only port 1883 (TLS enabled)
        '''
        if isinstance(self.client, mqtt_client.Client) and self.client.is_connected():
            try:
                self.disconnect()
            except Exception as e:
                _top_logger.warning(f"Fail to disconnect client")

        if (not isinstance(self.client, mqtt_client.Client)) or (MqttClient.current_cert_type!=cert_type):
            # we need to reconfigure SSL so we need a new client !
            if cert_type == "bootstrapping":
                self.new_client(my_cert_path=self.bootstrap_cert, my_key_path=self.bootstrap_key)
            else:
                self.new_client(my_cert_path=self.thing_cert_path, my_key_path=self.thing_key_path)
            MqttClient.current_cert_type=cert_type
        
        self.client.loop_start()
        self.client.connect_async(
            host=self.uri,
            port=8883,
            keepalive=ping_in_sec,
            # bind_port=None,
            # clean_start=mqtt_client.MQTT_CLEAN_START_FIRST_ONLY,
            properties=None
        )

    def disconnect(self):
        ''' '''
        self.client.disconnect()
        self.client.loop_stop()
   

    def sub(self, topics:List[str]=None, qos=1):
        ''' '''
        for t in topics:
            try:
                (result, mid) = self.client.subscribe(t, qos=qos)
                if result!=0:
                    # we have error
                    raise ConnectionError(mqtt_client.error_string(result))
                MqttClient.mid[mid] = f"Subscribe|{t}"
                if isinstance(self.topics[t].on_message, Callable):
                    self.client.message_callback_add(t, self.topics[t].on_message)
            except Exception as e:
                MqttClient.feedbackQueue.put_nowait({ 
                    "scope": f"Subscribe|{t}", 
                    "code": e,
                    "data": f"ERROR {e} when subscribe to {t}"
                })

    def unsub(self, topics:List[str]=None):
        ''' '''
        for t in topics:
            self.client.unsubscribe(t)

    def pub(self, topic:str, message:str, qos=1):
        ''' '''
        try:
            m_info:mqtt_client.MQTTMessageInfo = self.client.publish(topic, message, qos=qos)
            if m_info.rc!=0:
                # we have error
                raise ConnectionError(mqtt_client.error_string(m_info.rc))
            MqttClient.mid[m_info.mid] = f"Send|{topic}"
        except Exception as e:
            MqttClient.feedbackQueue.put_nowait({ 
                "scope":f"Incoming|{topic}", 
                "code":e,
                "data": f"ERROR {e} when subscribe to {topic}"
            })
