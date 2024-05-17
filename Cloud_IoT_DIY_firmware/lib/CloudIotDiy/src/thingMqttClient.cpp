/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#include "thingMqttClient.hpp"
#ifdef LOG_STACK_SIZE
void * StackPtrAtStartMqtt;
void * StackPtrEndMqtt;
UBaseType_t watermarkStartMqtt;
#endif
// Uncomment next line to log mqtt messages to serial
// #define MQTT_VERBOSE_LOGGING

TheThing* ThingMqttClient::thing;
String ThingMqttClient::thisThingCert;
String ThingMqttClient::thisThingKeys;
WiFiClientSecure ThingMqttClient::secureWifiClient;
PubSubClient ThingMqttClient::psClient;

String ThingMqttClient::telemetryTopic = "";
String ThingMqttClient::statusTopic = "";
String ThingMqttClient::commandTopic = "";
String ThingMqttClient::broadcastTopic = "";

/** Update precompiled topic template with current Thing properties */
String ThingMqttClient::updateTopicForThing(String someTopic) {
    // template could be "cmd/diyiot/{{ building_id }}/{{ location_id }}/diy/{{ thing_type }}/{{ thing_name }}"
    someTopic.replace("{{ thing_name }}", ThingMqttClient::thing->name);
    someTopic.replace("{{ things_group_name }}", ThingMqttClient::thing->group); //! NOTE that for now group is already prefilled!
    someTopic.replace("{{ thing_type }}", ThingMqttClient::thing->type);
    someTopic.replace("{{ building_id }}", ThingMqttClient::thing->buildingId);
    someTopic.replace("{{ location_id }}", ThingMqttClient::thing->locationId);
    return String(someTopic);
}
/**
 * Basic and the only constructor
*/
ThingMqttClient::ThingMqttClient(TheThing* oneThing, String thingCert, String thingKeys) {
    ThingMqttClient::thing = oneThing;
    thisThingCert = thingCert;
    thisThingKeys = thingKeys;
}
bool ThingMqttClient::connect() {
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtStartMqtt = (void *)&SpStart;
    watermarkStartMqtt =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrEndMqtt = StackPtrAtStartMqtt - watermarkStartMqtt;  
    Serial.printf("Free Stack near collectBackendConfig start is:  %d \r\n",  (uint32_t)StackPtrAtStartMqtt - (uint32_t)StackPtrEndMqtt);
#endif
    // 1. Use WiFiClientSecure class to create TCP MTLS connections
    DEBUGPRINTLN("Use secureWifiClient to create TCP MTLS connections");
    // secureWifiClient = WiFiClientSecure();
    // We'll be using certificates bundle (trusted store)
    DEBUGPRINTLN("-- We'll be using certificates bundle (trusted store)");
    delay(100);
    secureWifiClient.setCACertBundle(rootca_crt_bundle_start);
    // We'll add Thing certificate and key as client data
    // DEBUGPRINTLN(thingKeys.c_str());
    DEBUGPRINTLN("-- We'll add thing certificate as client data");
    // DEBUGPRINTLN(thingCert.c_str());
    delay(100);
    secureWifiClient.setCertificate(thisThingCert.c_str());
    DEBUGPRINTLN("-- We'll add thing key as client data");
    delay(100);
    secureWifiClient.setPrivateKey(thisThingKeys.c_str());
    // 2. Start MQTT connection with host using thing certificate/keys
    // NOTE that it's extremely important to provide name for the client!
    DEBUGPRINTLN("We'll start PubSubClient with secureWifiClient");
    delay(100);
    const char* mqttHost = MQTT_URL;
    psClient.setBufferSize(1024*4);    // increase max MQTT message size to 4Kb
    psClient.setServer(mqttHost, 8883);
    psClient.setClient(secureWifiClient);
    int connectionAttempts = 3;
    while (!(psClient.connected()) && connectionAttempts>0) {
        CHANGE_STATUS_LED();
        DEBUGPRINTLN("Will try to connect with named client '"+thing->name+"'");
        if (psClient.connect((char*) thing->name.c_str())) {
            DEBUGPRINT("Thing MQTT client connected to host: " + String(MQTT_URL) + "with state ");
            DEBUGPRINTLN(psClient.state());
        } else {
            DEBUGPRINT("Thing MQTT client FAIL to connect to host '" + String(MQTT_URL) + String("' with rc="));
            DEBUGPRINTLN(psClient.state());
            DEBUGPRINTLN("Will retry in 3 seconds");
        }
        connectionAttempts--;
        delay(500);
        CHANGE_STATUS_LED();
        delay(500);
    }
    if (!psClient.connected()) {
        DEBUGPRINT("Thing MQTT client FAIL to connect to host" + String(MQTT_URL));
        return false;
    }
    // 3. Assign standard callback
    DEBUGPRINTLN("Assign standard callback");
    psClient.setCallback(ThingMqttClient::commonCallback);
    // 4. assemble topic names
    // - control topic "cmd/diyiot/{{ building_id }}/{{ location_id }}/diy/{{ thing_type }}/{{ thing_name }}"
    commandTopic = String(CONTROL_TOPIC);
    commandTopic = updateTopicForThing(commandTopic);
    broadcastTopic = String(BROADCAST_TOPIC);
    broadcastTopic = updateTopicForThing(broadcastTopic);
    telemetryTopic = String(TELEMETRY_TOPIC);
    telemetryTopic = updateTopicForThing(telemetryTopic);
    statusTopic = String(STATUS_TOPIC);
    statusTopic = updateTopicForThing(statusTopic);
    // 5. Subscribe for control topic
    DEBUGPRINTLN("Subscribe to commandTopic");
    DEBUGPRINTLN(commandTopic);
    if (!psClient.subscribe(commandTopic.c_str())) {
        DEBUGPRINTLN("FAIL TO SUBSCRIBE to commandTopic");
        psClient.disconnect();
        return false;
    }
    // 6. Subscribe for broadcast topic
    DEBUGPRINTLN("Subscribe to broadcastTopic");
    DEBUGPRINTLN(broadcastTopic);
    if (!psClient.subscribe(broadcastTopic.c_str())) {
        DEBUGPRINTLN("FAIL TO SUBSCRIBE to broadcastTopic");
        psClient.disconnect();
        return false;
    }
    DEBUGPRINTLN(connected()?"I am CONNECTED":"I am NOT CONNECTED");
    return true;
}

/**
 * Common callback function which will invoke particular method on associated Thing
*/
void ThingMqttClient::commonCallback(char* topic, byte* payload, unsigned int length) {
    String messageReceived = String(payload, length);
    String receivedFromTopic = String(topic);

    // For debugging purposes we'll log received data
    //! NOTE debugging should be turned off on 'production' systems
    if (DEBUG_THING_MQTT_CLIENT) {
        DEBUGPRINTLN("Message arrived on '"+receivedFromTopic+"'");
        DEBUGPRINTLN(messageReceived);
    }
    ThingMqttClient::thing->commandReceived(messageReceived, receivedFromTopic);
}
/**
* Send message to Telemetry Topic
*/
bool ThingMqttClient::sendTelemetryMessage(String message) {
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtStartMqtt = (void *)&SpStart;
    watermarkStartMqtt =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrEndMqtt = StackPtrAtStartMqtt - watermarkStartMqtt;  
    Serial.printf("Free Stack near collectBackendConfig start is:  %d \r\n",  (uint32_t)StackPtrAtStartMqtt - (uint32_t)StackPtrEndMqtt);
#endif
    if (!psClient.connected()) {
        DEBUGPRINTLN("Client was disconnected. Will try to reconnect...");
        if(!connect()) return false;
    }
#ifdef MQTT_VERBOSE_LOGGING
    DEBUGPRINTLN("Publish to: "+telemetryTopic);
    DEBUGPRINTLN("Message: "+message);
#endif
    if (!psClient.publish(telemetryTopic.c_str(), message.c_str())){
        DEBUGPRINTLN("FAIL TO PUBLISH to "+telemetryTopic);
        psClient.disconnect();
        return false;
    }
    ;
    //TODO - QoS control to be added before returning the True
    return true;
}
/**
* Send message to Status Topic
*/
bool ThingMqttClient::sendStatusMessage(String message){
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtStartMqtt = (void *)&SpStart;
    watermarkStartMqtt =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrEndMqtt = StackPtrAtStartMqtt - watermarkStartMqtt;  
    Serial.printf("Free Stack near collectBackendConfig start is:  %d \r\n",  (uint32_t)StackPtrAtStartMqtt - (uint32_t)StackPtrEndMqtt);
#endif
    if (!psClient.connected()) {
        DEBUGPRINTLN("Client was disconnected. Will try to reconnect...");
        if(!connect()) return false;
    }
#ifdef MQTT_VERBOSE_LOGGING
    DEBUGPRINTLN("Publish to: "+statusTopic);
    DEBUGPRINTLN("Message: "+message);
#endif
    if (!psClient.publish(statusTopic.c_str(), message.c_str())){
        DEBUGPRINTLN("FAIL TO PUBLISH to "+statusTopic);
        psClient.disconnect();
        return false;
    }
    //TODO - QoS control to be added before returning the True
    return true;
}