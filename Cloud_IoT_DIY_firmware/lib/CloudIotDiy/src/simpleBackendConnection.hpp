/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
#ifndef SIMPLE_BACKEND_CONNECTION
#define SIMPLE_BACKEND_CONNECTION

#include <WiFi.h>
// https://github.com/espressif/arduino-esp32/tree/master/libraries/WiFiClientSecure
// #include <WiFiClientSecure.h>
#include <Arduino.h>
// libraries required for configuring WiFi over BLE
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <Preferences.h>
// libraries required to configure Backend with local Web Server
#include <AsyncTCP.h>
#include "ESPAsyncWebServer.h"
// libraries required to communicate with Cloud Backend
#include "ArduinoJson.hpp"

/************************************************/
// Project components
#include "_projectData.hpp"
#include "configHardwareConstants.hpp"
#include "htmlFormBasic.hpp"
#include "theThing.hpp"
#include "fleetProvisioning.hpp"
#include "thingMqttClient.hpp"
#include "thingSerialConfigClient.hpp"
/************************************************/

/*
* Class to 
* - handle Cloud Backend parameters collected from nvs memory or Web Server
* - 
*/
class SimpleBackendConnection {
  private:
    const char* IPSERVICE_UUID = "e32cfg00-1fb5-459e-8fcc-c5c9c330efgh";  // 2 12 36 bytes only
    const char* IP_UUID = "beb5483e-36e1-4688-b7f5-ea0736122222";       //"Enter the name of 2GHz WiFi endpoint"
    const char* BCKEND_NAMESPACE = "BCKEND";// nvs namespace for Cloud Backend connection data
    const char* MQTT_ENDPOINT = "MQTTURL";  // key for backend MQTT URL in the BCKEND namespace
    const char* API_ENDPOINT = "APIURL";    // key for backend MQTT URL in the BCKEND namespace
    const char* MYCERT_KEY = "MYCERT";      // key for device cert value in the BCKEND namespace
    const char* MYKEY_KEY = "MYPKEY";       // key for device private key value in the BCKEND namespace
    const char* THINGHASH_KEY = "THINGHASH";// key for hash of the current Thing definition in the BCKEND namespace

    int webServerPort = 80;

    // URL of MQTT host
    String bckendMqttUrl;
    // URL of MTLS API
    String bckendApiUrl;
    // Device certificate
    String myCert;
    // Device key
    String myPrivateKey;
    
    // Connection features
    bool supportMqtt = false;
    bool supportApi = false;
    bool enableFleetProvisioning = true;


    // Thing for this connection
    TheThing* thing;

    /*
    * This method will 
    * - start the Web Server with configuration form
    * - start the BLE Server with IP info
    * - wait for all required data available and write it to nvs
    * @return false if config failed
    */
    bool collectBackendConfig(int port);

  public:    
    // Thing MQTT client
    ThingMqttClient mqtt;  // it may be reasonable to make it private but re-exposing methods is boring

    SimpleBackendConnection(boolean mqtt, boolean api);

    inline void disableFleetProvisioning() { enableFleetProvisioning = false; }
    /**
    * - collect required data from nvs (call collectBackendConfig if needed)
    * - provision the Thing if needed !!!
    */
    void setup(TheThing* oneThing, int localWebServerPort);
    /**
    * - instantiate MQTT Client
    * - subscribe to Command Topic
    * - publish message to Status Plane
    * @param 
    * @return False if connection or subscription failed
    */
    bool startMqttClient();
    /**
     * - execute 'collect data' for the thing
     * - assemble the telemetry message payload
     * - send MQTT message to the telemetry topic
    */
    bool collectAndSendTelemetryData(float sendTimeout=10000, bool doNotSend=false);
    /**
     * 
    */
    void unprovision();
    /**
     * @brief run MQTT loop and/or check API
     * NOTE that for now it's just MQTT loop
     * 
     * @return true 
     * @return false 
     */
    bool update();
};

#endif