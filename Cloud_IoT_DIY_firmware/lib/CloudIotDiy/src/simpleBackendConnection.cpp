/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
#include "simpleBackendConnection.hpp"
/*
*==================================================
*SOME IMPORTANT NOTES REGARDING THIS IMPLEMENTATION
1. this backend connection works as all-in-one for different scenarios (first start/provisioning, reprovisioning, normal operations)
2. one of the serious challenges is MEMORY allocation (limitations)
 -  initial fleet provisioning may fail due to memory issue. 
    That's not a very big problem IF claim cert/key was stored - after the restart the system will provision itself
 -  if system fails to store the cert and key - sometimes helps restart and provision again
 -  if system cannot provision - you may need to decrease the footprint (remove some libraries), provision and than update the code
    provisioning information will be available in the NVS and system will just update it status
3. there is a potential conflict between thing info provided during provisioning and defined in main.cpp (if defined)
    this may result in strange behavior: system will be first provision itself with data provided 
    but than reprovision itself with data from constructor in main.cpp
    as a result you can have some "ghost" devices in the cloud registry
    so BE CAREFUL and either use same parameters in main.cpp and during provisioning OR use empty constructor in main.cpp
*==================================================
*/

// Starting BLE server just to publish thing's IP address may be an overkill
// and it takes memory :(
// BUT it'll be published if next line uncommented
// #define PUBLISH_IP_OVER_BLE

#ifdef LOG_STACK_SIZE
void * StackPtrAtStart;
void * StackPtrEnd;
UBaseType_t watermarkStart;
#endif
/*******************************************************************/
// define some values for Cloud Backend Parameters
// Preferences lib for non-volatile data is used as we're using ESP32
// For other microcontrollers you maybe need EEPROM lib
/*******************************************************************/
Preferences backendConnectionInfo;

/*
* This method will 
* - check if we don't have 'claim certificate'
*   - start the Web Server with configuration form
*   - start the BLE Server with IP info
*   - wait for all required data available and write it to nvs
*     one of certificates required (device or claim)
* - if we have 'claim certificate' but not device one - start auto-provisioning process
*/
bool SimpleBackendConnection::collectBackendConfig(int port) {
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtStart = (void *)&SpStart;
    watermarkStart =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrEnd = StackPtrAtStart - watermarkStart;  
    Serial.printf("Free Stack near collectBackendConfig start is:  %d \r\n",  (uint32_t)StackPtrAtStart - (uint32_t)StackPtrEnd);
#endif
    DEBUGPRINTLN("Start collectBackendConfig");
    AsyncWebServer* configServer = new AsyncWebServer(port);
    String myIP = WiFi.localIP().toString() + "port" + String(port);
    String myMAC = WiFi.macAddress();
    FleetProvisioning* provThing = new FleetProvisioning();
    if (enableFleetProvisioning && provThing->readyToProvision() && thing->minPropsAvailable()) {
        // we have all required data for Fleet Provisioning
        CHANGE_STATUS_LED();
        DEBUGPRINTLN("Start FleetProvisioning");
        bool provResult;
        try {
            provResult = provThing->provisionThing(thing);
        }
        catch(const std::exception& e) {
            DEBUGPRINTLN("Fleet provisioning failed with exception");
            DEBUGPRINTLN(e.what());
            provResult = false;
        }
        if(provResult) {
            DEBUGPRINTLN("Fleet provisioning successful. Will write Cert/Keys to NVS");
            DEBUGPRINTLN(provThing->thingCert);
            DEBUGPRINTLN(provThing->thingKeys);
            myCert = provThing->thingCert;
            myPrivateKey = provThing->thingKeys;
            backendConnectionInfo.putString(MYKEY_KEY, provThing->thingKeys);
            backendConnectionInfo.putString(MYCERT_KEY, provThing->thingCert);
            CHANGE_STATUS_LED();
            return true;
        } else {
            // fleet provisioning failed
            DEBUGPRINTLN("Automatic 'fleet' provisioning failed. Continue with manual...");
            CHANGE_STATUS_LED();
        }
    }
    delete provThing;
    /*************************************************************************/
    CHANGE_STATUS_LED();
    // BLE SERVER
#ifdef PUBLISH_IP_OVER_BLE
    // Start BLE server with IP address info
    DEBUGPRINTLN("Start BLE server to provide IP "+myIP);
    // Create BLE Server to collect WiFi configuration
    BLEDevice::init("ESP32 config");
    BLEServer *ipServer = BLEDevice::createServer();
    BLEService *ipService = ipServer->createService(IPSERVICE_UUID);
    BLECharacteristic *ipCharacteristic = ipService->createCharacteristic( IP_UUID, BLECharacteristic::PROPERTY_READ );
    ipCharacteristic->setValue((char *)myIP.c_str());
    // Start service
    ipService->start();
    // Advertise service
    BLEAdvertising *ipAdvertising = ipServer->getAdvertising();
    ipAdvertising->start();
#endif
    /*************************************************************************/
    // WEB SERVER
    DEBUGPRINTLN("Configure Web Server");
    // Route for root / web page
    HtmlFormBasic bckndConfigForm(THING_CONFIG_ENDPOINT);
    bckndConfigForm.addParameter("Thing Name:", "ThingName", "ThingName", "text", "Enter unique name of your Thing...", thing->name==""?"Thing"+myMAC:thing->name);
    bckndConfigForm.addParameter("Thing Group:", "ThingGroup", "ThingGroup", "text", "Enter the group of your Thing...", thing->group);
    bckndConfigForm.addParameter("Thing Type:", "ThingType", "ThingType", "text", "Enter the type of your Thing...", thing->type);
    bckndConfigForm.addParameter("BuildingId:", "ThingBuilding", "ThingBuilding", "text", "Enter buildingId for your Thing...", thing->buildingId);
    bckndConfigForm.addParameter("LocationId:", "ThingLocation", "ThingLocation", "text", "Enter locationId for your Thing...", thing->locationId);
    if (supportMqtt) bckndConfigForm.addParameter("MQTT URL:", "URL", "MqttUrl", "text", "URL of MQTT host", bckendMqttUrl);
    if (supportApi) bckndConfigForm.addParameter("API URL:", "URL", "ApiUrl", "text", "URL of things API", bckendApiUrl);
    if (enableFleetProvisioning) bckndConfigForm.addParameter("Claim Cert:", "CLCERT", "ClaimCert", "text", "Copy your claim certificate here...");
    if (enableFleetProvisioning) bckndConfigForm.addParameter("Claim Keys:", "CLKEYS", "ClaimKeys", "text", "Copy your claim keys here...");
    bckndConfigForm.addParameter("Device Cert:", "DCERT", "DeviceCert", "text", "Copy your device certificate here...");
    bckndConfigForm.addParameter("Device Keys:", "PKEY", "PrivateKey", "text", "Copy your device private key here...");
    configServer->on("/", HTTP_GET, bckndConfigForm.formRequestHandler);
    // add an endpoint for serving POST request
    // NOTE that this endpoint can be used as an API
    configServer->on(bckndConfigForm.formSubmitPath(), HTTP_POST, bckndConfigForm.formSubmitHandler);
    
    // start web server
    DEBUGPRINTLN("Start Web Server on "+myIP); // IP "+myIP+" and port "+String(port));
    configServer->begin();

    // init serial config client
    DEBUGPRINTLN("Start Web Server on "+myIP); // IP "+myIP+" and port "+String(port));
    ThingSerialConfig serialConfig;

    /*************************************************************************/
    // wait for all field being provided
    String thingName, thingGroup, thingType, thingBuilding, thingLocation, claimCert, claimKeys;
    bool thingConfigured = false;
    bool urlsConfigured = false;
    bool fleetProvConfigured = false;
    bool thingCertConfigured = false;
    int attemptN = 0;
    bool mqttUrlUpdated = false;
    bool apiUrlUpdated = false;
    bool fleetProv = false;
    // HtmlFormBasic *htmlSource=&bckndConfigForm;
    // ThingSerialConfig *serialSource=&serialConfig;
    do {
        attemptN++;
        CHANGE_STATUS_LED();
        delay(200);
        if (Serial.available()>0) serialConfig.collect();
        // Choose the source of configuration data (Serial if data available, Html Form else)
        try {
            // TRY to COLLECT REQUIRED DATA
            thingName = serialConfig.configDataAvailable?serialConfig.valueFor("ThingName"):bckndConfigForm.valueFor("ThingName");
            thingGroup = serialConfig.configDataAvailable?serialConfig.valueFor("ThingGroup"):bckndConfigForm.valueFor("ThingGroup");
            thingType = serialConfig.configDataAvailable?serialConfig.valueFor("ThingType"):bckndConfigForm.valueFor("ThingType");
            thingBuilding = serialConfig.configDataAvailable?serialConfig.valueFor("ThingBuilding"):bckndConfigForm.valueFor("ThingBuilding");
            thingLocation = serialConfig.configDataAvailable?serialConfig.valueFor("ThingLocation"):bckndConfigForm.valueFor("ThingLocation");
            // Fleet prov required params
            if (enableFleetProvisioning) {
                claimCert = serialConfig.configDataAvailable?serialConfig.valueFor("ClaimCert"):bckndConfigForm.valueFor("ClaimCert");
                claimKeys = serialConfig.configDataAvailable?serialConfig.valueFor("ClaimKeys"):bckndConfigForm.valueFor("ClaimKeys");
            }
            // URLs
            if (supportMqtt) {
                String updMqttUrl = serialConfig.configDataAvailable?serialConfig.valueFor("MqttUrl"):bckndConfigForm.valueFor("MqttUrl");
                mqttUrlUpdated = bckendMqttUrl != updMqttUrl;
                bckendMqttUrl = updMqttUrl;
            }
            if (supportApi) {
                String updSupportApi = serialConfig.configDataAvailable?serialConfig.valueFor("ApiUrl"):bckndConfigForm.valueFor("ApiUrl");
                apiUrlUpdated = bckendApiUrl != updSupportApi;
                bckendApiUrl = updSupportApi;
            }
            // Thing keys
            myPrivateKey = serialConfig.configDataAvailable?serialConfig.valueFor("PrivateKey"):bckndConfigForm.valueFor("PrivateKey");
            myCert = serialConfig.configDataAvailable?serialConfig.valueFor("DeviceCert"):bckndConfigForm.valueFor("DeviceCert");
        } catch(const std::exception& e) {
            DEBUGPRINTLN("`EXCEPTION when collecting data provided...");
            DEBUGPRINTLN(e.what());
        }
                
        try {
            // Certificates and keys can come with '|' in place of '\n'
            claimCert.replace("|","\n");
            claimKeys.replace("|","\n");
            myPrivateKey.replace("|","\n");
            myCert.replace("|","\n");
        }
        catch(const std::exception& e) {
            DEBUGPRINTLN("`EXCEPTION when updating data provided...");
            DEBUGPRINTLN(e.what());
        }
        
        // check if we have all required data
        thingConfigured = thingName.length()>0&&thingGroup.length()>0&&thingType.length()>0&&thingBuilding.length()>0&&thingLocation.length()>0;
        urlsConfigured = (!supportMqtt||bckendMqttUrl.length()>0)&&(!supportApi||bckendApiUrl.length()>0);
        if (enableFleetProvisioning) fleetProvConfigured = claimCert.length()>0&&claimKeys.length()>0;
        thingCertConfigured = myCert.length()>0&&myPrivateKey.length()>0;
        if (thingConfigured && urlsConfigured && !thingCertConfigured && fleetProvConfigured) {
            // run fleet provisioning
            DEBUGPRINTLN("Store 'fleet' provisioning data");
            // delay(200);
            try {
                provThing = new FleetProvisioning(claimCert, claimKeys);
                // instead of starting the Fleet provision here we can just restart the thing
                // it may be reasonable as otherwise memory allocation mey fail during provisioning
                fleetProv = true;
                break;
            } catch(const std::exception& e) {
                DEBUGPRINTLN("`EXCEPTION with automatic 'fleet' provisioning. Continue with manual...");
                DEBUGPRINTLN(e.what());
            }
        } else {
            if (((attemptN%100)==0) || attemptN==1) {
                DEBUGPRINTLN("");
                DEBUGPRINT("Waiting for configuration data. Data not available yet for: ");
                if (!thingConfigured) DEBUGPRINT("Thing ");
                if (!urlsConfigured) DEBUGPRINT("URLs ");
                if (!thingCertConfigured) DEBUGPRINT("ThingCert ");
                if (!fleetProvConfigured) DEBUGPRINT("ClaimCert ");
                // DEBUGPRINTLN(".");
            } else if ((attemptN%9)==0) DEBUGPRINT(".");
        }
    } while (!((thingConfigured && urlsConfigured && (fleetProvConfigured||thingCertConfigured||fleetProv))));
    DEBUGPRINTLN("Config data collected");
    // delay(100);
    /*************************************************************************/

    // Stop BLE Server
#ifdef PUBLISH_IP_OVER_BLE
        ipService->stop();
        BLEDevice::deinit(true);
#endif
    // Stop Web Server
    configServer->end();
    delete configServer;
    // write collected data to nvs
    if (thingConfigured) thing->updateIfNeeded(thingName, thingGroup, thingType, thingBuilding, thingLocation);
    if (supportMqtt&&urlsConfigured&&mqttUrlUpdated) backendConnectionInfo.putString(MQTT_ENDPOINT, bckendMqttUrl);
    if (supportApi&&urlsConfigured&&apiUrlUpdated) backendConnectionInfo.putString(API_ENDPOINT, bckendApiUrl);
    if (fleetProv) {
        if(provThing->provisionThing(thing)) {
            myPrivateKey = provThing->thingKeys;
            myCert = provThing->thingCert;
            thingCertConfigured = true;
        } else {
            DEBUGPRINTLN("Automatic 'fleet' provisioning failed. Restart thing...");
            ESP.restart();
        }
        delete provThing;
    }
    // we have device cert and keys
    backendConnectionInfo.putString(MYKEY_KEY, myPrivateKey);
    backendConnectionInfo.putString(MYCERT_KEY, myCert);
    if (attemptN%2!=0) CHANGE_STATUS_LED();
    return true;
}

SimpleBackendConnection::SimpleBackendConnection(boolean mqtt, boolean api) {
    supportMqtt = mqtt;
    supportApi = api;
}

void SimpleBackendConnection::setup(TheThing* oneThing, int localWebServerPort) {
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtStart = (void *)&SpStart;
    watermarkStart =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrEnd = StackPtrAtStart - watermarkStart;  
    Serial.printf("Free Stack near setup start is:  %d \r\n",  (uint32_t)StackPtrAtStart - (uint32_t)StackPtrEnd);
#endif
    thing = oneThing;
    webServerPort = localWebServerPort;
    // start from an attempt to collect backend parameters from nvs
    backendConnectionInfo.begin(BCKEND_NAMESPACE, false);
    // check if we forced OR HAVE TO to collect backend parameters
    // Check if Thing were redefined 
    //  button has been pressed option is available in main.cpp
    if (thing->reprovision) { // || digitalRead(BUTTON_PIN) == LOW) { 
        //while (digitalRead(BUTTON_PIN) == LOW) ; // Wait for button to be released
        DEBUGPRINTLN("reprovision is true! Cleanup stored backend params. This will start Web Server for backend config");
        backendConnectionInfo.clear();
    }
    // URLs are part of the Project configuration but we provide an option to overwrite it
    DEBUGPRINTLN("Try to collect data from nvs");
    bckendMqttUrl = backendConnectionInfo.getString(MQTT_ENDPOINT, MQTT_URL);
    DEBUGPRINTLN(bckendMqttUrl);
    bckendApiUrl = backendConnectionInfo.getString(API_ENDPOINT, MTLS_API_URL);
    DEBUGPRINTLN(bckendApiUrl);
    // Absence of device certificate and key always trigger configuration process
    myCert = backendConnectionInfo.getString(MYCERT_KEY, "");
    // DEBUGPRINTLN(myCert);
    myPrivateKey = backendConnectionInfo.getString(MYKEY_KEY, "");
    // DEBUGPRINTLN(myPrivateKey);

    boolean mqttDataNeeded = supportMqtt && (bckendMqttUrl.length()==0);
    boolean apiDataNeeded = supportApi && (bckendApiUrl.length()==0);
    if (myCert.length()==0 || myPrivateKey.length()==0 || mqttDataNeeded || apiDataNeeded) collectBackendConfig(webServerPort);
    DEBUGPRINTLN("SimpleBackendConnection::setup completed");
}

/**
* - instantiate MQTT Client
* - subscribe to Command Topic
* - publish message to Status Plane
* @param 
* @return False if connection or subscription failed
*/
bool SimpleBackendConnection::startMqttClient() {
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtStart = (void *)&SpStart;
    watermarkStart =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrEnd = StackPtrAtStart - watermarkStart;  
    Serial.printf("Free Stack near startMqttClient start is:  %d \r\n",  (uint32_t)StackPtrAtStart - (uint32_t)StackPtrEnd);
#endif
    DEBUGPRINTLN("Start MQTT client with");
    // DEBUGPRINTLN(myCert);
    // DEBUGPRINTLN(myPrivateKey);
    mqtt = ThingMqttClient(thing, myCert, myPrivateKey);
    mqtt.connect();
    DEBUGPRINTLN(mqtt.connected()?"CONNECTED":"NOT CONNECTED");
    if (mqtt.connected()) {
        // as we have a client connected we need to identify if we need to send status message with updated thing info
        // start from an attempt to collect backend parameters from nvs
        backendConnectionInfo.begin(BCKEND_NAMESPACE, false);
        String lastThingHash = backendConnectionInfo.getString(THINGHASH_KEY, "");
        if (lastThingHash != thing->thingDefinitionHash()) {
            // Thing was changed we need to inform backend
            String message = "{\"content\":\"update-model\",\"data\":"+thing->modelToJsonString()+"}";
            DEBUGPRINTLN("SimpleBackendConnection::send update-model message: "+message);
            if(mqtt.sendStatusMessage(message)) {
                update();
                //! we'll update NVS without confirmation from the cloud backend
                backendConnectionInfo.putString(THINGHASH_KEY, thing->thingDefinitionHash());
            } else {
                DEBUGPRINTLN("FAIL to send updated model to backend!");
            }
        }
        backendConnectionInfo.end();
    }
    return mqtt.connected();
};

/**
 * - execute 'collect data' for the thing
 * - assemble the telemetry message payload
 * - send MQTT message to the telemetry topic
*/
bool SimpleBackendConnection::collectAndSendTelemetryData(float sendTimeout, bool doNotSend) {
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtStart = (void *)&SpStart;
    watermarkStart =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrEnd = StackPtrAtStart - watermarkStart;  
    Serial.printf("Free Stack near collectAndSendTelemetryData start is:  %d \r\n",  (uint32_t)StackPtrAtStart - (uint32_t)StackPtrEnd);
#endif
    //1. Collect data
    DEBUGPRINTLN("collectAndSendTelemetryData: will try to collect data");
    try {
        if (thing->collectData("")) {
            // we're good
        } else {
            DEBUGPRINTLN("Was not able to collect telemetry data");
            return false;
        }
    } catch(const std::exception& e){
        DEBUGPRINTLN("FAIL to collect telemetry data with exception");
        DEBUGPRINTLN(e.what());
        return false;
    }
    //2. Assemble telemetry message payload
    String messagePayload = thing->latestDataToJsonString();
    DEBUGPRINTLN("MQTT payload will be: "+messagePayload);
    // ArduinoJson is an overkill here!
    // // get latest collected data and calculate its size
    // std::map<String, String> messageData = thing->latestData();
    // int dataSize = 0;
    // for (const auto& item : thing->latestData()) {
    //     dataSize += item.first.length();
    //     dataSize += item.second.length();
    // }
    // // create 
    // DynamicJsonDocument payload(dataSize*1.2);
    // for (const auto& item : thing->latestData())
    //   payload[item.first] = item.second;
    // serializeJson(payload, messagePayload);

    //3. Send MQTT message
    if (!doNotSend) {
        try {
            if (mqtt.sendTelemetryMessage(messagePayload)) {
                //we're good
            } else {
                DEBUGPRINTLN("Was not able to send telemetry data");
                return false;
            }
        } catch(const std::exception& e){
            DEBUGPRINTLN("FAIL to send telemetry data with exception");
            DEBUGPRINTLN(e.what());
            return false;
        }
    }
    return true;
}

/**
 * 
*/
void SimpleBackendConnection::unprovision() {
    DEBUGPRINTLN("unprovision: Cleanup stored backend params. This will start Web Server for backend config");
    backendConnectionInfo.clear();
}

/**
 * @brief run MQTT loop and/or check API
 * NOTE that for now it's just MQTT loop
 * 
 * @return true 
 * @return false 
 */
bool SimpleBackendConnection::update() {
    if (mqtt.connected()) return mqtt.loop();
    return false;
}
