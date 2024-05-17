/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
#ifndef CONFIGURE_WIFI_CONNECTION
#define CONFIGURE_WIFI_CONNECTION

/************************************************/
#include <WiFi.h>
// https://github.com/espressif/arduino-esp32/tree/master/libraries/WiFiClientSecure
// #include <WiFiClientSecure.h>
#include <Arduino.h>
// libraries required for configuring WiFi over BLE
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <Preferences.h>
/************************************************/

/************************************************/
// Project components
#include "configHardwareConstants.hpp"
#include "_projectData.hpp"
/************************************************/

/**
 * 
*/
class ConfigureWifiConnection {
  private:
    const char* SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c330abcd";    // 2 12 36 bytes only
    const char* SSID_UUID = "beb5483e-36e1-4688-b7f5-ea0736100000";       //"Enter the name of 2GHz WiFi endpoint"
    const char* SSIDPASS_UUID = "beb5483e-36e1-4688-b7f5-ea0736111111";   //"Enter the WiFi access key (password)"
    const char* PREF_NAMESPACE = "ESP32_WIFI";  // nvs namespace for WiFi connection data
    const char* SSID_KEY = "SSID";              // key for SSID value in the ESP32_WIFI namespace
    const char* SSIDPASS_KEY = "SSIDKEY";       // key for SSID value in the ESP32_WIFI namespace

  // WiFi network name and password (WiFi parameters are stored in the nvs memory)
    String mySSID="";
    String myPass="";

  public:

    // IP assigned when thing finally connected to WiFi
    IPAddress myIp;
    String myMAC;
    /*
    * This constructor implements WiFi Params collection logic
    *  - check if button was pressed when boot - clear nvs data if yes
    *  - check if we don't have WiFi connection info available in nvm OR 
    *  - start initial config step if needed which will start BLE Server, 
    *  - wait for the required info, 
    *  - write them down to nvm and stop BLE Server
    */
    ConfigureWifiConnection();

    /*
    * Start the WiFi connection with parameters collected by constructor
    */
    boolean start();
};

#endif