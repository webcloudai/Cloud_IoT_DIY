/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#ifndef FLEET_PROVISIONING
#define FLEET_PROVISIONING
// When debugging enabled Serial will be used to log
#define DEBUG_FLEET_PROVISIONING true

/************************************************/
#include "WiFiClientSecure.h"
#include "PubSubClient.h"
#include <Preferences.h>
#include <Arduino.h>
#include <ArduinoJson.h>
/************************************************/

/************************************************/
// Project components
#include "_projectData.hpp"
#include "theThing.hpp"
#include "configHardwareConstants.hpp"
/************************************************/

class FleetProvisioning {
  private:
    const char* FLEETPROV_NAMESPACE = "FLEETPROV";  // nvs namespace for Fleet Provisioning
    // const char* PROV_HOST_URL = "PROVURL";       // key for host URL in the FLEETPROV_NAMESPACE
    const char* CLAIM_CERT_KEY = "CLAIMCERT";       // key for claim certificate in the FLEETPROV_NAMESPACE
    const char* CLAIM_KEYS_KEY = "CLAIMKEYS";       // key for claim cert keys in the FLEETPROV_NAMESPACE
    const unsigned long maxResponseWait = 18000;    // limit response waiting by this number of millis

    String hostURL=MQTT_URL;
    String claimCert;
    String claimCertKeys;

  public:
    // Properties for fleet provisioning results
    // static properties are used by callback function
    static String messageReceived;
    static String receivedFromTopic;
    // these properties will be filled when/if provisioning succeeded
    String thingCert="";
    String thingKeys="";

    /*
    * Basic constructor which will collect all required values from NVS
    */
    FleetProvisioning() {
        hostURL = MQTT_URL;
        updateFromNvs();
    }
    /*
    * Constructor with Claim Certificate and Keys provided
    */
    FleetProvisioning(String claimCertificate, String claimKeys) {
        claimCert = claimCertificate;
        claimCertKeys = claimKeys;
        hostURL = MQTT_URL;
        updateNvsFromProps();
    }
    /**
     * Check if we have minimal data required for provisioning
    */
    inline bool readyToProvision() {
        return claimCert.length()>0&&claimCertKeys.length()>0&&hostURL.length()>0;
    }
    /*
    * This method will implement required MQTT messages exchange for
    * 'fleet provisioning' process using 'claim certificate'
    * @param {TheThing} oneThing - thing to provision
    */
    bool provisionThing(TheThing* oneThing);

    /*
    * collect properties from NVS
    */
    inline void updateFromNvs() {
        /*******************************************************************/
        // define some values for Thing
        // Preferences lib for non-volatile data is used as we're using ESP32
        // For other microcontrollers you maybe need EEPROM lib
        /*******************************************************************/
        Preferences fleetProvInfo;
        fleetProvInfo.begin(FLEETPROV_NAMESPACE, true);
        claimCert = fleetProvInfo.getString(CLAIM_CERT_KEY, "");
        claimCertKeys = fleetProvInfo.getString(CLAIM_KEYS_KEY, "");
        // hostURL = fleetProvInfo.getString(PROV_HOST_URL, "");
        fleetProvInfo.end();
    }
    /*
    * write current properties to NVS
    */
    inline void updateNvsFromProps() {
        Preferences fleetProvInfo;
        fleetProvInfo.begin(FLEETPROV_NAMESPACE, false);
        fleetProvInfo.putString(CLAIM_CERT_KEY, claimCert);
        fleetProvInfo.putString(CLAIM_KEYS_KEY, claimCertKeys);
        // fleetProvInfo.putString(PROV_HOST_URL, hostURL);
        fleetProvInfo.end();
    }
    /*
    * Clear all data from NVS Thing Namespace
    */
    inline void clearThingNvs() {
        Preferences fleetProvInfo;
        fleetProvInfo.begin(FLEETPROV_NAMESPACE, false);
        fleetProvInfo.clear();
        fleetProvInfo.end();
    }
    
};

#endif