/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#include "thingSerialConfigClient.hpp"

/**
 * @brief collect value for some config parameter
 * 
 */
String ThingSerialConfig::valueFor(String paramName, bool partial, String defaultValue) {
    if (receivedData.find(paramName)==receivedData.end()) return defaultValue;
    else return receivedData[paramName];
}

/**
 * @brief call this method when expecting config over serial AND serial data available
 * In general you'll have some loop in code where you'll check if serial available
 * and call collect if yes
 */
void ThingSerialConfig::collect() {
    String collected="";
    delay(100);
    if (Serial.available() > 0) {
        collected = Serial.readString();
        if (collected==String(CONFIG_SESSION_REQUEST)) {
            // we have request for serial communications
            // OR for serial communications with session already opened (this may happen)
            commSession = true;
            // 1. Confirm
            Serial.println(CONFIG_SESSION_CONFIRM);
            // 2. Clear collected data
            receivedData.clear();
            configDataAvailable = false;
            return;
        }
        if (!commSession) {
            // this is unexpected - neither data from config session
            // nor request for session
            // we'll just ignore this
            Serial.println("UNEXPECTED INPUT. IGNORED!");
            return;
        }
        // so we have communication session opened
        if (dataTransmission) {
            // we have first piece of data in collected but we may have more
            unsigned long startTime = millis();
            do {
                //* NOTE that we expect every collected string be of format
                //* <property name>:::<property value>
                //* I.e. both names and values are strings with ':::' as separator
                if (collected!="") {
                startTime = millis();
                // lookup for property name
                // const char* inputStr = collected.c_str();
                int j = -2;
                for (int i=0; i<collected.length() && j<=0; i++ ) {
                    if(collected.charAt(i)==':') {
                    if (j<0) j++;
                    else if (j==0) j=i-2;
                    }
                }
                if (j<=0 || j>=collected.length()) {
                    // wrong input format - ignored but we need to response with error
                    Serial.println("WRONG INPUT");
                    // Serial.println(collected);
                } else {
                    // expected response - two lines: prop name and prop value
                    Serial.println(collected.substring(0,j));
                    Serial.println(collected.substring(j+3));
                    receivedData[collected.substring(0,j)] = collected.substring(j+3);
                }
                collected = "";
                }
                // 3. Collect extra data if any
                if (Serial.available() > 0) {
                collected = Serial.readString();
                //reset timeout counter
                startTime = millis();
                if (collected==String(CONFIG_SESSION_CLOSE)) {
                    dataTransmission = false;
                } else {
                    //more data will be covered in the next cycle
                }
                } else {
                // we can do something here but for now just wait a little
                delay(10);
                }
            } while (((millis()-startTime)<SERIAL_COMM_TIMEOUT_MS)&&dataTransmission);
            if (!receivedData.empty()) {
                configDataAvailable = true;
                // send back collected data for validation before closing session
                Serial.println(CONFIG_SESSION_CLOSE);
                Serial.println("===================");
                for (const auto &elem : receivedData) {
                Serial.printf("'%s':'%s'",elem.first,elem.second);
                Serial.println("");
                } //Serial.printf("%s:%s",elem.first,elem.second);
                Serial.println("===================");
            }
            // close data transmission session
            dataTransmission = false;
            commSession = false;
            return;
        }
        // We have session but not data transmission
        dataTransmission = (collected==String(CONFIG_SESSION_START_DATA));
        // 2. We'll wait for 'start data transmission' for some time
        unsigned long startTime = millis();
        while (((millis()-startTime)<SERIAL_COMM_TIMEOUT_MS)&&!dataTransmission) {
            if (Serial.available() > 0) {
                collected = Serial.readString();
                dataTransmission = (collected==String(CONFIG_SESSION_START_DATA));
            } else {
                delay(100);
            }
        }
        // Session closed if we didn't get 'start data transmission' in SERIAL_COMM_TIMEOUT_MS
        if (!dataTransmission) Serial.println(CONFIG_SESSION_CLOSE);
        else Serial.println(CONFIG_SESSION_START_DATA);
        commSession = dataTransmission;
    }
}

