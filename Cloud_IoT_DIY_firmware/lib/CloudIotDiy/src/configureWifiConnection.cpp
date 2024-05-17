/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#include "configureWifiConnection.hpp"

/*******************************************************************/
// Preferences lib for non-volatile data is used as we're using ESP32
// you may need EEPROM lib for other microcontrollers 
static Preferences wifiConnectionInfo;                 


/********************************************************************************/
// Provision step 1 - Connect your device to Internet
/*
* Class to handle callbacks for update of SSID/SSID_KEY field over BLE
*/
class ConfigCallbacksWifi: public BLECharacteristicCallbacks {
    public:
      const char*  nvsKey;
    void onWrite(BLECharacteristic *pCharacteristic) {
      std::string value = pCharacteristic->getValue();
      if (value.length() > 0) {
        String ssid = String(strcpy(new char[value.length() + 1], value.c_str()));
        wifiConnectionInfo.putString(nvsKey, ssid);
        DEBUGPRINTLN("");
        DEBUGPRINT("Configuration value collected and stored in nvs memory");
      }
    }
};

/*
* Class to 
* - handle WiFi parameters collected from nvs memory or BLE
* - WiFi connection
*/
ConfigureWifiConnection::ConfigureWifiConnection() {
    // start from an attempt to collect WiFi parameters from nvs
    wifiConnectionInfo.begin(PREF_NAMESPACE, false);

    // Add some logic to enable Thing WiFi RECONNECTION with button click
    // Turn ON the green light and wait 1 sec for button pressed
    BaseHardware::TURN_RGBLED_OFF();
    BaseHardware::CHANGE_GREEN_LED();
    for(int i=0; i<10 && digitalRead(BUTTON_PIN) == LOW; i++) delay(100);
    if (digitalRead(BUTTON_PIN) == LOW) { 
        // If button has been pressed we'll use some 'hidden' logic for reset stored WiFi parameters
        // if the button pressed and released three times - WiFi params will be removed
        for (int resetCounter=3; digitalRead(BUTTON_PIN) == LOW; resetCounter--) {
            while (digitalRead(BUTTON_PIN) == LOW) {
                // Confirm button pressed and wait for button to be released
                BaseHardware::CHANGE_GREEN_LED();
                delay(100);
            }
            if (resetCounter<0) {
                    // cleanup WiFi params
                    DEBUGPRINTLN("Cleanup stored WiFi params. This will start BLE for WiFi config");
                    wifiConnectionInfo.clear();
            }
            // flash the led to confirm the count
            BaseHardware::BLINK_GREEN_LED(10, 300);
        }
        // proceed without reprovisioning
        BaseHardware::TURN_RGBLED_OFF();
    }

    mySSID = wifiConnectionInfo.getString(SSID_KEY, "");
    myPass = wifiConnectionInfo.getString(SSIDPASS_KEY, "");

    if (mySSID == "" || myPass == "") {
        //! It can be nvs read error
        /*
        * This part of code implements BLE for WiFi parameters collection
        * If BLE not available Serial can be used for WiFi configuration
        */
        BaseHardware::TURN_RGBLED_OFF();
        BaseHardware::CHANGE_GREEN_LED();
        DEBUGPRINTLN("Start BLE server to collect WiFi configuration");
        // Create BLE Server to collect WiFi configuration
        BLEDevice::init("ESP32 config");
        BLEServer *pServer = BLEDevice::createServer();
        BLEService *pService = pServer->createService(SERVICE_UUID);
        // Add BLE writable BLE characteristic to collect WiFi SSID
        // Note that we are using ConfigCallbacksWifi class with nvsKey for callbacks
        ConfigCallbacksWifi callBckSsid;
        callBckSsid.nvsKey = SSID_KEY;
        BLECharacteristic *ssidCharacteristic = pService->createCharacteristic(
                                                SSID_UUID,
                                                BLECharacteristic::PROPERTY_READ |
                                                BLECharacteristic::PROPERTY_WRITE
                                            );
        ssidCharacteristic->setCallbacks(&callBckSsid);
        ssidCharacteristic->setValue("Enter the name of 2GHz WiFi endpoint");

        // Add BLE writable BLE characteristic to collect WiF password
        // Note that we are using ConfigCallbacksWifi class with nvsKey for callbacks
        ConfigCallbacksWifi callBckWifiKey;
        callBckWifiKey.nvsKey = SSIDPASS_KEY;
        BLECharacteristic *passCharacteristic = pService->createCharacteristic(
                                                SSIDPASS_UUID,
                                                BLECharacteristic::PROPERTY_READ |
                                                BLECharacteristic::PROPERTY_WRITE
                                            );
        passCharacteristic->setCallbacks(&callBckWifiKey);
        passCharacteristic->setValue("Enter the WiFi access key (password)");
        // Start service
        pService->start();
        // Advertise service
        BLEAdvertising *pAdvertising = pServer->getAdvertising();
        pAdvertising->start();
        // Callback classes will handle value collection and write values to nvs
        // So we just waiting until wifi data available in Preferences
        DEBUGPRINT("Waiting for WiFi config data over BLE");
        while (mySSID == "" || myPass == "") {
            //! THIS IS BAD endless loop if WiFi not available!
            // TODO: make it smarter or at least 
            //* time-boxed with restart to resolve potential nvs read errors
            delay(2000);
            mySSID = wifiConnectionInfo.getString(SSID_KEY, "");
            myPass = wifiConnectionInfo.getString(SSIDPASS_KEY, "");
            DEBUGPRINT(".");
        }
        // Stop BLE Server
        pService->stop();
        // End nvs connection
        wifiConnectionInfo.end();
        DEBUGPRINTLN("");
        DEBUGPRINTLN("Configuration over BLE completed.");
        DEBUGPRINTLN("================================="); 
        BaseHardware::TURN_RGBLED_OFF();
    }
}

/*
* Start the WiFi connection with parameters collected by constructor
*/
boolean ConfigureWifiConnection::start() {
    DEBUGPRINTLN("================================="); 
    DEBUGPRINTLN("Connecting to WiFi network: " + mySSID);

    // casting value from String to char* is required
    WiFi.begin((char *)mySSID.c_str(), (char *)myPass.c_str());

    BaseHardware::TURN_RGBLED_OFF();
    while (WiFi.status() != WL_CONNECTED) {
        // Blink Blue LED while we're connecting:
        //! THIS IS BAD endless loop if WiFi not available!
        // TODO: make it smarter
        BaseHardware::CHANGE_BLUE_LED();
        delay(500);
        DEBUGPRINT(".");
    }
    myIp = WiFi.localIP();
    myMAC = WiFi.macAddress();

    DEBUGPRINTLN();
    DEBUGPRINTLN("WiFi connected!");
    DEBUGPRINT("IP address: ");
    DEBUGPRINTLN(myIp);
    return true;
}
