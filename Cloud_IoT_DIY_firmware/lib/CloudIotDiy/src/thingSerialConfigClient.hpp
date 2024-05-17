/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#ifndef THE_THING_SERIAL_CONFIG
#define THE_THING_SERIAL_CONFIG

#include <map>
#include <Arduino.h>

/************************************************/
// Project components
#include "_projectData.hpp"
#include "thingConfig.hpp"
/************************************************/

/**
 * @brief 
 * 
 */
class ThingSerialConfig : public ThingConfig {

  protected:
    /**
     * @brief data collected in config session
     * 
     */
    std::map<String,String> receivedData={};
    /**
     * @brief do we have a communication session opened
     * 
     */
    bool commSession = false;
    /**
     * @brief do we have a data transmission internal session opened
     * 
     */
    bool dataTransmission = false;

  public:
    /**
     * @brief do we have config data collected properly
     * 
     */
    bool configDataAvailable = false;
    /**
     * @brief Construct a new Thing Serial Config object
     * 
     */
    ThingSerialConfig() {
        // receivedData = {};
        // commSession = false;
        // dataTransmission = false;
        // configDataAvailable = false;
    }
    /**
     * @brief call this method when expecting config over serial AND serial data available
     * In general you'll have some loop in code where you'll check if serial available
     * and call collect if yes
     */
    void collect();
    /**
     * @brief collect value for some config parameter
     * 
     */
    String valueFor(String paramName, bool partial=true, String defaultValue="");
};

#endif