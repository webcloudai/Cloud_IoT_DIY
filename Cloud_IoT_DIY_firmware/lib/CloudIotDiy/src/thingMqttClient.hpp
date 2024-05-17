/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#ifndef THING_MQTT_CLIENT
#define THING_MQTT_CLIENT
// When debugging enabled Serial will be used to log
#define DEBUG_THING_MQTT_CLIENT true

#include "WiFiClientSecure.h"
#include "PubSubClient.h"
#include <Preferences.h>
#include <Arduino.h>
#include "_projectData.hpp"
#include "theThing.hpp"
#include "configHardwareConstants.hpp"
#include <ArduinoJson.h>

/**
 * Singleton class - MQTT client for this specific Thing
*/
class ThingMqttClient {
    private:
        // Thing for this connection
        static TheThing* thing;
        static String thisThingCert;
        static String thisThingKeys;
        /**
         * 
        */
        static WiFiClientSecure secureWifiClient;
        /**
         * https://pubsubclient.knolleary.net/api
        */
        static PubSubClient psClient;

        static String telemetryTopic;
        static String statusTopic;
        static String commandTopic;
        static String broadcastTopic;
        /** Update precompiled topic template with current Thing properties */
        static String updateTopicForThing(String someTopic);

    public:
        /**
         * Common callback function which will invoke particular method on associated Thing
        */
        static void commonCallback(char* topic, byte* payload, unsigned int length);


        /**
         * Basic and the only constructor
        */
        ThingMqttClient(TheThing* oneThing, String thingCert, String thingKeys);
        // default one just to have an opportunity to instantiate
        ThingMqttClient() { }
        /**
         * Connect to host and subscribe to required topics
        */
        bool connect();
        /**
         * Disconnect MQTT client
        */
        inline void disconnect() {
            try {
                psClient.disconnect();
            }
            catch(const std::exception& e) {
                DEBUGPRINTLN("Got an exception trying to disconnect PubSubClient");
                DEBUGPRINTLN(e.what());
            }
        }
        /**
         * Check if client connected
        */
        inline bool connected() { return ThingMqttClient::psClient.connected(); }
        /**
         * @brief run backend loop for PubSubClient
         * 
         * @return true 
         * @return false
         */
        inline bool loop() { return psClient.loop(); }

        /**
        * Send message to Telemetry Topic
        */
        bool sendTelemetryMessage(String message);
        /**
        * Send message to Status Topic
        */
        bool sendStatusMessage(String message);

};

#endif
