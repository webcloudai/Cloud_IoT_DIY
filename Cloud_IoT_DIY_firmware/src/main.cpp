/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
//! NOTE that some parameters (including enabling Serial Logging is defined in lib/CloudIotDiy/src/_projectData.hpp)
#include <Arduino.h>

SET_LOOP_TASK_STACK_SIZE(8192*3); // Required! As we're using WiFiClientSecure https://esp32.com/viewtopic.php?t=28250
/* 
UNCOMMENT TO CLEAN UP ALL DATA FROM NVS 
AND DON'T FORGET TO COMMENT IT BACK !!!
*/
// #define CLEAN_UP_WHOLE_NVS_CONTENT
#ifdef CLEAN_UP_WHOLE_NVS_CONTENT
#include <nvs_flash.h>
#endif
//
/*
COMMENT NEXT LINE TO DEVELOP LOCALLY WITHOUT BOTHERING YOUR CLOUD BACKEND
THIS WILL DISABLE CLOUD COMMUNICATIONS INCLUDING WIFI CONNECTION
*/
#define CLOUD_ENABLED
//
/************************************************/
// Project components
#include "configHardwareConstants.hpp"
#include "configureWifiConnection.hpp"
#include "simpleBackendConnection.hpp"
#include "theThing.hpp"
/************************************************/
// MY THING DESCRIPTION
// different things will have different files (setup code change may also be required)
#include "myThing001.hpp"
/************************************************/

// initialize RGB LED STATUS
bool BaseHardware::IS_RGB_LED_ON = false;

/**********************************************************************************************/
// define global backend connection client with both MQTT and API access
SimpleBackendConnection bckend(true, true);

// We are using here constructor with values for the Thing
//! This should be used with care - if values in NVS are different and overwrite=true the Thing will be re-provisioned!!!
// You may use basic constructor instead (values will be collected from NVS): OneThing myThing = OneThing();
// However - in that case required parameters will be requested during backend setup !
OneThing myThing = OneThing("Bme280Thing00", APP_ID, "DiyThing", "building001", "location000", true);

// we need a marker if data need to be collected and send
bool sendData = true;
// we need to limit thing wakeup time
unsigned long thingBootTime;

/*
* Arduino style 'setup' function
*/
void setup() {
  // Initialize Serial connection
  SERIALBEGIN(115200);
  // Initialize hardware:
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW); // Turn off LED
  
  #ifdef CLEAN_UP_WHOLE_NVS_CONTENT
  // THIS BLOCK WILL BE ENABLED ONLY IF YOU'LL WANT TO ERASE NVS
  BaseHardware::TURN_RGBLED_ON(1);
  DEBUGPRINTLN("Cleaning up the all data from NVS after 5 seconds...");
  const esp_err_t a = nvs_flash_erase(); // erase the NVS partition and...
  const esp_err_t b = nvs_flash_init();  // initialize the NVS partition.
  DEBUGPRINTLN("Clean up completed. Please load the updated firmware.");
  while(true) {
    BaseHardware::CHANGE_RED_LED();
    DEBUGPRINT(".");
    delay(100);
  };
  #endif
  
  // Collect WiFi parameters (stored in the nvs memory)
  // Note that we just defining the class instance here
  // Class constructor will control WiFi parameters collection logic
  ConfigureWifiConnection wifiParams;
  
#ifdef CLOUD_ENABLED
  // Connect to the WiFi network
  // NOTE that for now wifiParams.start() never returns False but it may in the future
  DEBUGPRINTLN("MAIN - Connect to the WiFi network");
  if (!wifiParams.start()) //! No reason to check for now but with better start logic it can be!
    DEBUGPRINTLN("MAIN - FAIL TO CONNECT TO WIFI !");
    
  // Collect Cloud Backend parameters (stored in the nvs memory)
  // Preconfigured Thing is REQUIRED as it's main properties are required for connection setup
  // Web Server in local network will run on port 80
  myThing.reprovision = false;
  DEBUGPRINTLN("MAIN - setup backend");
  bckend.setup(&myThing, 80);
#endif
  /************************************************/
  // define this Thing
  DEBUGPRINTLN("MAIN - define this Thing");
  myThing.defineThing(wifiParams.myMAC);
  /************************************************/
  // Log the Thing config
  DEBUGPRINTLN("MAIN - Full thing definition: " + myThing.thingToJsonString());
  DEBUGPRINTLN("MAIN - Full thing hash: " + myThing.thingDefinitionHash());

#ifdef CLOUD_ENABLED
  // Start MQTT with backend
  // Verify that collected data works and push/retrieve additional configuration
  DEBUGPRINTLN("MAIN - Start MQTT with backend");
  if (!bckend.startMqttClient()) {
    DEBUGPRINTLN("MAIN - FAIL TO CONNECT TO CLOUD BACKEND ! Will go sleep.");
    myThing.goSleep();
  }
  // When/if mqtt client started successfully there are two options:
  // 1. (recommended) use bckend to send/receive data (like bckend.collectAndSendTelemetryData())
  // 2. use mqtt client directly (like bckend.mqtt->sendTelemetryMessage(String message))
  // We'll be using the first option in the loop
#endif

  DEBUGPRINTLN("*********** setup completed ***********");
  digitalWrite(STATUS_LED_PIN, LOW); // LED off
  thingBootTime = millis();
}

void loop() {
  // potentially we don't need loop for this particular Thing
  // we'll just use it once to
  // 1. Collect and send collected data to bckend
  // 2. We'll also wait a little to give commands a chance to be executed
  // 3. Close backend connection
  // 4. Go to deep sleep

  if (sendData) {
    // Add some logic to enable Thing reprovision with button click
    // Turn ON the red light and wait 3 sec for button pressed
    BaseHardware::TURN_RGBLED_ON(1);
    for(int i=0; i<10 && digitalRead(BUTTON_PIN) == HIGH; i++) delay(300);
    if (digitalRead(BUTTON_PIN) == LOW) { 
      // Check if button has been pressed
      // We'll use some 'hidden' logic for reset device provisioning
      // When in the loop device will control if button pressed
      // if the button pressed and released three times - provisioning will be removed
      for (int resetCounter=3; digitalRead(BUTTON_PIN) == LOW; resetCounter--) {
        while (digitalRead(BUTTON_PIN) == LOW) {
          // Confirm button pressed and wait for button to be released
          BaseHardware::CHANGE_RED_LED();
          delay(100);
        }
        if (resetCounter<0) {
          // 'unprovision' device and restart
          DEBUGPRINTLN("LOOP:INFO - device unprovision requested");
          bckend.unprovision();
          ESP.restart();
        }
        // flash the led to confirm the count
        BaseHardware::BLINK_RED_LED(10, 300);
      }
      // proceed without reprovisioning
    }
    BaseHardware::TURN_RGBLED_OFF();
    // Collecting/sending data is really simple 
    //  we'll be using default send timeout of 10sec
    //  if local running requested "doNotSend will be true"
    float sendTimeout = 10000.0F;
#ifdef CLOUD_ENABLED
    bool doNotSend = false;
#else
    bool doNotSend = true;
#endif
    if (!bckend.collectAndSendTelemetryData(sendTimeout, doNotSend)) {
      DEBUGPRINTLN("LOOP:ERROR - Fail to collect/send telemetry to the backend");
      // here the logic of storing unsent data could be added but we'll just drop it
    } else {
      // mark that data sent and we don;t need to collect/send it again
      sendData = false;
    }
  }

  // run backend update to check for any upcoming messages
  if (!bckend.update()) {
    // we have an issue with backend connection !
    DEBUGPRINTLN("LOOP:WARNING - we have an issue with backend connection");
  }
  // check if we need to collect telemetry again
  if ((millis()-thingBootTime)>myThing.getMeasuringInterval()) {
    // we'll measure again
    thingBootTime = millis();
    sendData = true;
  } else {
    // check if we've waited enough to go to sleep
    if ((millis()-thingBootTime)>myThing.getMaxAwakeTime()) {
      if ((millis()-thingBootTime)<myThing.getMeasuringInterval()) {
        // go deep sleep
        DEBUGPRINTLN("LOOP:INFO - It's time to go sleep.");
        myThing.goSleep();
      } 
    }
    // flash the led to mark that we'll do another loop
    BaseHardware::BLINK_GREEN_LED(5,100);
  }
}

