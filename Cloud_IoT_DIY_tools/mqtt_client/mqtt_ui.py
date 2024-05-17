'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
from __future__ import annotations
from typing import Dict, List, Callable, Union
import PySimpleGUI as sg

class MqttLayout:
    '''
    Layout will include:
    - multiple scrolling multi-lines
    - for each multiline:
        - mqtt-channel label
        - mqtt-payload input text
        - send button
    '''
    def __init__(self, *,
            layout_title:str,
            mqtt_host:str,
            mqtt_channels_prov:List[List[(str, str)]] = [ 
                    [("channel1", "payload"), ("channel2", "payload"), ("channel3", "payload")], 
                    [("channel4", "payload"), ("channel5", "payload"), ("channel6", "payload")] 
                ],
            mqtt_channels_work:List[List[(str, str)]] = [ 
                    [("channel1", "payload"), ("channel2", "payload"), ("channel3", "payload")], 
                    [("channel4", "payload"), ("channel5", "payload"), ("channel6", "payload")] 
                ]
        ) -> None:
        ''' mqtt_channels top level list define columns with each next level list defines row'''
        
        self.layout = []
        columns_work = [[] for _ in mqtt_channels_work[0]]
        for clmn in mqtt_channels_work:
            for i,(mqtt_topic, mqtt_payload) in enumerate(clmn):
                columns_work[i].append( 
                    sg.Column([
                        [sg.Text(mqtt_topic, key=f"Label|{mqtt_topic}", enable_events=True, size=(70,1))],
                        [sg.Multiline(mqtt_payload or "N/A", key=f"Payload|{mqtt_topic}", size=(70,5 if mqtt_payload else 1), disabled=mqtt_payload is None, enable_events=True)],
                        [
                            sg.Button("Subscribe", key=f"Subscribe|{mqtt_topic}", enable_events=True), 
                            sg.Button("Send", key=f"Send|{mqtt_topic}", enable_events=True, disabled=mqtt_payload is None),
                            sg.Button("Unsubscribe", key=f"Unsubscribe|{mqtt_topic}", enable_events=True), 
                        ],
                        [sg.Multiline("", key=f"Incoming|{mqtt_topic}", size=(70,9), disabled=True, enable_events=True)]
                    ])
                )
        columns_prov = [[] for _ in mqtt_channels_prov[0]]
        for clmn in mqtt_channels_prov:
            for i,(mqtt_topic, mqtt_payload) in enumerate(clmn):
                columns_prov[i].append( 
                    sg.Column([
                        [sg.Text(mqtt_topic, key=f"Label|{mqtt_topic}", enable_events=True, size=(70,1))],
                        [sg.Multiline(mqtt_payload or "N/A", key=f"Payload|{mqtt_topic}", size=(70,5 if mqtt_payload else 1), disabled=mqtt_payload is None, enable_events=True)],
                        [
                            sg.Button("Subscribe", key=f"Subscribe|{mqtt_topic}", enable_events=True), 
                            sg.Button("Send", key=f"Send|{mqtt_topic}", enable_events=True, disabled=mqtt_payload is None),
                            sg.Button("Unsubscribe", key=f"Unsubscribe|{mqtt_topic}", enable_events=True), 
                        ],
                        [sg.Multiline("", key=f"Incoming|{mqtt_topic}", size=(70,9), disabled=True, enable_events=True)]
                    ])
                )        
        self.prov_connect_incoming = f"IncomingProv|{mqtt_host}"
        self.work_connect_incoming = f"IncomingWork|{mqtt_host}"

        self.layout = [[ 
            sg.TabGroup( 
                [[ 
                    sg.Tab(
                        "PROVISION",
                        [
                            [ sg.Text(layout_title)],
                            [
                                sg.Text(text=mqtt_host, key=f"Label|{mqtt_host}", enable_events=True, size=(70,1)),
                                sg.Button("ConnectProv", key=f"connect_prov", enable_events=True), 
                                sg.Button("DisconnectProv", key=f"disconnect_prov", enable_events=True, disabled=True)
                            ],
                            [sg.Multiline("", key=self.prov_connect_incoming, size=(130,3), disabled=True, enable_events=True)],
                        ] + [clmn for clmn in columns_prov]
                    ),
                    sg.Tab(
                        "WORK",
                        [
                            [ sg.Text(layout_title)],
                            [
                                sg.Text(text=mqtt_host, key=f"Label|{mqtt_host}", enable_events=True, size=(70,1)),
                                sg.Button("ConnectWork", key=f"connect_work", enable_events=True), 
                                sg.Button("DisconnectWork", key=f"disconnect_work", enable_events=True, disabled=True)
                            ],
                            [sg.Multiline("", key=self.work_connect_incoming, size=(130,3), disabled=True, enable_events=True)]
                        ] + [clmn for clmn in columns_work]
                    )
                ]] 
            ) 
        ]]
