/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
#include "fleetProvisioning.hpp"

#ifdef LOG_STACK_SIZE
void * StackPtrAtTheStart;
void * StackPtrTheEnd;
UBaseType_t watermarkAtStart;
#endif

String FleetProvisioning::messageReceived="";
String FleetProvisioning::receivedFromTopic="";


/**
 * Common callback function which will update static property of FleetProvisioning
*/
void commonCallback(char* topic, byte* payload, unsigned int length) {
    // For debugging purposes we'll log received data
    //! NOTE debugging should be turned off as Cert and Key logged otherwise
    if (DEBUG_FLEET_PROVISIONING) {
        DEBUGPRINT("Message arrived [");
        DEBUGPRINT(topic);
        DEBUGPRINT("] ");
        for (int i=0;i<length;i++) {
            DEBUGPRINT((char)payload[i]);
        }
        DEBUGPRINTLN();
    }
    FleetProvisioning::messageReceived = String(payload, length);
    FleetProvisioning::receivedFromTopic = String(topic);
}

/*
* This method will implement required MQTT messages exchange for
* 'fleet provisioning' process using 'claim certificate'
* @param {TheThing} oneThing - thing to provision
*/
bool FleetProvisioning::provisionThing(TheThing* oneThing) {
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtTheStart = (void *)&SpStart;
    watermarkAtStart =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrTheEnd = StackPtrAtTheStart - watermarkAtStart;  
    Serial.printf("Free Stack near provisionThing start is:  %d \r\n",  (uint32_t)StackPtrAtTheStart - (uint32_t)StackPtrTheEnd);
#endif
    // 0. Use WiFiClientSecure class to create TCP MTLS connections
    DEBUGPRINTLN("Use WiFiClientSecure class to create TCP MTLS connections");
    delay(300);
    WiFiClientSecure wifiClient;
    // We'll be using certificates bundle (trusted store)
    DEBUGPRINTLN("-- We'll be using certificates bundle (trusted store)");
    delay(300);
    wifiClient.setCACertBundle(rootca_crt_bundle_start);
    // We'll add claim certificate and key as client data
    DEBUGPRINTLN("-- We'll add claim certificate as client data");
    delay(300);
    wifiClient.setCertificate(claimCert.c_str());
    DEBUGPRINTLN("-- We'll add claim key as client data");
    delay(300);
    wifiClient.setPrivateKey(claimCertKeys.c_str());
    // 1. Start MQTT connection with host using claim certificate
    // NOTE that it's extremely important to provide name for the client!
    DEBUGPRINTLN("Start MQTT connection with host using claim certificate");
    delay(300);
    const char* mqttHost = MQTT_URL;
    PubSubClient mqttClient(mqttHost, 8883, wifiClient);
    int connectionAttempts = 3;
    while (!mqttClient.connected() && connectionAttempts>0) {
        CHANGE_STATUS_LED();
        if (mqttClient.connect((char*) oneThing->name.c_str())) {
            mqttClient.setBufferSize(1024*16);
            DEBUGPRINTLN("FleetProvisioning MQTT connected to host: " + String(MQTT_URL));
        } else {
            DEBUGPRINT("FleetProvisioning FAIL to connect to MQTT host" + String(MQTT_URL) + String(" with rc="));
            DEBUGPRINTLN(mqttClient.state());
            DEBUGPRINTLN("Will retry in 3 seconds");
        }
        connectionAttempts--;
        delay(1500);
        CHANGE_STATUS_LED();
        delay(1500);
    }
    if (!mqttClient.connected())
        return false;
    // 2. Subscribe to two topics CERT_REQ_ACCEPTED_TOPIC and CERT_REQ_REJECTED_TOPIC
    DEBUGPRINTLN("Subscribe to two topics CERT_REQ_ACCEPTED_TOPIC and CERT_REQ_REJECTED_TOPIC: ");
    DEBUGPRINTLN(CERT_REQ_ACCEPTED_TOPIC);
    DEBUGPRINTLN(CERT_REQ_REJECTED_TOPIC);

    FleetProvisioning::messageReceived = "";
    FleetProvisioning::receivedFromTopic = "";
    mqttClient.setCallback(commonCallback);
    if (!mqttClient.subscribe(CERT_REQ_ACCEPTED_TOPIC)) {
        DEBUGPRINTLN("FAIL TO SUBSCRIBE to CERT_REQ_ACCEPTED_TOPIC");
        mqttClient.disconnect();
        return false;
    }
    if (!mqttClient.subscribe(CERT_REQ_REJECTED_TOPIC)) {
        DEBUGPRINTLN("FAIL TO SUBSCRIBE to CERT_REQ_REJECTED_TOPIC");
        mqttClient.disconnect();
        return false;
    }
    // 3. Publish empty message to topic CERT_REQUEST_TOPIC
    DEBUGPRINTLN("Publish empty message to topic CERT_REQUEST_TOPIC: ");
    DEBUGPRINTLN(CERT_REQUEST_TOPIC);
    if (!mqttClient.publish(CERT_REQUEST_TOPIC,"")){
        DEBUGPRINTLN("FAIL TO PUBLISH to CERT_REQUEST_TOPIC");
        mqttClient.disconnect();
        return false;
    }
    // 4. Collect parameters from message in CERT_REQ_ACCEPTED_TOPIC
    //      Certificate and Keys are important but we don't write them to nvs on this step
    //    aggregate payload of particular format for provisioning request
    //    Handle error if message arrives into CERT_REQ_REJECTED_TOPIC instead
    bool waitForResponse = true;
    unsigned long started = millis();
    String provPayload = "";
    while (waitForResponse || ((millis()-started)>maxResponseWait)) {
        mqttClient.loop();
        if (FleetProvisioning::receivedFromTopic.equalsIgnoreCase(CERT_REQ_REJECTED_TOPIC)) {
            // we have an issue - request rejected :(
            // message received from some other topic ???
            DEBUGPRINT("FleetProvisioning certificate request REJECTED with message ");
            DEBUGPRINTLN(FleetProvisioning::messageReceived);
            return false;
        } else if (FleetProvisioning::receivedFromTopic.equalsIgnoreCase(CERT_REQ_ACCEPTED_TOPIC)) {
            // request confirmed! Let's deserialize the payload
            // we need quite large buffer as payload contains cert and key 
            StaticJsonDocument<8192> certResponse;
            // Deserialize the JSON document
            DeserializationError deserError = deserializeJson(certResponse, FleetProvisioning::messageReceived);
            // Test if parsing succeeds.
            if (deserError) {
                DEBUGPRINT("FleetProvisioning FAIL to deserialize message with error ");
                DEBUGPRINTLN(deserError.f_str());
                return false;
            }
            // Fetch values.
            //
            // store received Thing Certificate and Keys
            thingCert = String(certResponse["certificatePem"].as<const char *>());
            thingKeys = String(certResponse["privateKey"].as<const char *>());
            // important value for provision request
            // char* certOwnershipToken = (char *)certResponse["certificateOwnershipToken"];
            // certResponse.clear();
            // create payload for provision message
            StaticJsonDocument<1024> provReqDoc;
            provReqDoc["certificateOwnershipToken"] = certResponse["certificateOwnershipToken"].as<const char *>();
            JsonObject reqParams = provReqDoc.createNestedObject("parameters");
            reqParams["appName"] = APP_ID;
            reqParams["thingName"] = oneThing->name;
            reqParams["thingSerial"] = WiFi.macAddress();
            reqParams["thingGroup"] = THINGS_GROUP_NAME;    // Always THINGS_GROUP_NAME when provisioning!
            reqParams["thingType"] = PROV_THING_TYPE;       // Always PROV_THING_TYPE when provisioning!
            reqParams["buildingId"] = oneThing->buildingId;
            reqParams["locationId"] = oneThing->locationId;
            // serialize object to string
            serializeJson(provReqDoc, provPayload);
            waitForResponse = false;
        } else if (FleetProvisioning::receivedFromTopic.length()>0) {
            // message received from some other topic ???
            DEBUGPRINT("FleetProvisioning UNEXPECTED message received from topic ");
            DEBUGPRINTLN(FleetProvisioning::receivedFromTopic);
            mqttClient.disconnect();
            return false;
        } else {
            DEBUGPRINT(".");
            delay(300);
        }
        // we maybe don't have a message yet but don't have anything to do but wait
    }
    if (waitForResponse) {
        // we didn't get a message - timeout
        DEBUGPRINT("FleetProvisioning TIMEOUT - did not receive the response for cert request");
        return false;
    }
    DEBUGPRINTLN("Unsubscribe from two topics CERT_REQ_ACCEPTED_TOPIC and CERT_REQ_REJECTED_TOPIC");
    mqttClient.unsubscribe(CERT_REQ_ACCEPTED_TOPIC);
    mqttClient.unsubscribe(CERT_REQ_REJECTED_TOPIC);
    // 5. Subscribe to two topics THING_PROV_ACCEPTED_TOPIC and THING_PROV_REJECTED_TOPIC
    FleetProvisioning::messageReceived = "";
    FleetProvisioning::receivedFromTopic = "";
    DEBUGPRINTLN("Subscribe to two topics THING_PROV_ACCEPTED_TOPIC and THING_PROV_REJECTED_TOPIC: ");
    DEBUGPRINTLN(THING_PROV_ACCEPTED_TOPIC);
    DEBUGPRINTLN(THING_PROV_REJECTED_TOPIC);
    if (!mqttClient.subscribe(THING_PROV_ACCEPTED_TOPIC)) {
        DEBUGPRINTLN("FAIL TO SUBSCRIBE to THING_PROV_ACCEPTED_TOPIC");
        mqttClient.disconnect();
        return false;
    }
    if (!mqttClient.subscribe(THING_PROV_REJECTED_TOPIC)) {
        DEBUGPRINTLN("FAIL TO SUBSCRIBE to THING_PROV_REJECTED_TOPIC");
        mqttClient.disconnect();
        return false;
    }
    // 6. Publish 'provisioning request' to topic THING_PROV_TOPIC
    DEBUGPRINTLN("Publish prepared message to topic THING_PROV_TOPIC: ");
    DEBUGPRINTLN(THING_PROV_TOPIC);
    if (!mqttClient.publish(THING_PROV_TOPIC, provPayload.c_str())){
        DEBUGPRINTLN("FAIL TO PUBLISH to THING_PROV_TOPIC");
        mqttClient.disconnect();
        return false;
    }
    // 7. Collect parameters from message in THING_PROV_ACCEPTED_TOPIC
    //    Handle error if message arrives into THING_PROV_REJECTED_TOPIC
    waitForResponse = true;
    started = millis();
    while (waitForResponse || ((millis()-started)>maxResponseWait)) {
        mqttClient.loop();
        if (FleetProvisioning::receivedFromTopic.equalsIgnoreCase(THING_PROV_REJECTED_TOPIC)) {
            // we have an issue - request rejected :(
            // message received from some other topic ???
            DEBUGPRINT("FleetProvisioning provisioning request REJECTED with message ");
            DEBUGPRINTLN(FleetProvisioning::messageReceived);
            return false;
        } else if (FleetProvisioning::receivedFromTopic.equalsIgnoreCase(THING_PROV_ACCEPTED_TOPIC)) {
            // request confirmed! Let's deserialize the payload
            waitForResponse = false;
        } else if (FleetProvisioning::receivedFromTopic.length()>0) {
            // message received from some other topic ???
            DEBUGPRINT("FleetProvisioning UNEXPECTED message received from topic ");
            DEBUGPRINTLN(FleetProvisioning::receivedFromTopic);
            return false;
        } else {
            DEBUGPRINT(".");
            delay(500);
        }
        // we maybe don't have a message yet but don't have anything to do but wait
    }
    DEBUGPRINTLN("Unsubscribe from two topics THING_PROV_ACCEPTED_TOPIC and THING_PROV_REJECTED_TOPIC");
    mqttClient.unsubscribe(THING_PROV_ACCEPTED_TOPIC);
    mqttClient.unsubscribe(THING_PROV_REJECTED_TOPIC);
    DEBUGPRINTLN("Disconnect from host");
    mqttClient.disconnect();

    // If provisioning successful - return TRUE
    //  writing device certificate and key to nvs is a responsibility of the caller !
    return !waitForResponse;
}
