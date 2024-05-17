/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
/*
*==================================================
*SOME IMPORTANT NOTES REGARDING THIS IMPLEMENTATION
In general - this is definition of your thing
However it's convenient to have a "generic start" which will help to create specific things
This implementation as a result contains a lot of conditional code (#ifdef)
BUT all of this maybe replaced with shorter implementation if you don't need any of this stuff
*==================================================
*/

#ifndef MYTHING_DEFINITION
#define MYTHING_DEFINITION

#include <Arduino.h>

// Components used for my thing definition (this part may be isolated in a separate file) 
#include <map>
#include <vector>
#include <numeric>

/************************************************/
// Project components
// #include "configHardwareConstants.hpp"
// #include "configureWifiConnection.hpp"
// #include "simpleBackendConnection.hpp"
#include "theThing.hpp"
/************************************************/
// THIS THING specific dependencies (based on some popular sensors and Sparkfun breakouts)
//----------------------------------
//
// At first ENS160 sensor usage, minimum 48 hours of "burn in" should be made. 
// Later, at each usage, ~3 min. of functioning should passed before sensor data may be considered as valid.
// To respect this requirements MaxAwakeTime and MeasuringInterval will be updated
//* NOTE that unlike BME680 ENS160 can be used in a power restricted devices. 
//* However it may be reasonable to use it with plugged-in controllers (like RPi)
#define ENS160BME280_THING

//
// At first BME680 sensor usage, minimum 48 hours of "burn in" should be made. 
// Later, at each usage, 30 min. of functioning should passed before sensor data may be considered as valid.
// To respect this requirements MaxAwakeTime will be updated to be greater than MeasuringInterval
//* NOTE that for BME680 the ONLY reasonable option will be plugged-in (PSU over USB) with NO SLEEP time
//! This NOTE effectively means that BME680 better be used with ANOTHER controller (like RPi)
//! IF you'll need to use BME680 with this thing - ADD LIBRARY to project !
// #define BME680_THING

// DHT22 consumes power when device in a sleep mode. To decrease consumption connect sensor power to GPIO !
// #define DHT22_THING

//
// #define TMP102_THING
//

/************************************************/
// THIS THING specific functions
//
// DHT22 thing
// dependencies: adafruit/Adafruit Unified Sensor AND adafruit/DHT sensor library
#ifdef DHT22_THING
#include "DHT.h"
#define DHTPIN 4 
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);
// DHTPOWERPIN is used to turn power off when deep sleep to decrease consumption
#define DHTPOWERPIN 39
#endif
//
// TMP102 thing
// dependencies: adafruit/DHT sensor library
#ifdef TMP102_THING
//#include <SparkFunTMP102.h> // Used to send and recieve specific information from our sensor
#include <Wire.h>
#include <Temperature_LM75_Derived.h>
Generic_LM75_9_to_12Bit_OneShot temperature;
#endif
//
// BME680 thing
// dependencies: adafruit/Adafruit BME680 Library@^2.0.2
//! NOTE that BME680 dependency is NOT added to project by default !!!
#ifdef BME680_THING
#ifndef TwoWire_h
#include <Wire.h>
#endif
#include <SPI.h>
#include <Adafruit_Sensor.h>
#include "Adafruit_BME680.h"
// #define BME_SCK 13
// #define BME_MISO 12
// #define BME_MOSI 11
// #define BME_CS 10
// #define SEALEVELPRESSURE_HPA (1013.25)
Adafruit_BME680 bme; // I2C
#endif
//
// ENS160/BME280 thing
// see https://docs.sparkfun.com/SparkFun_Environmental_Combo_Breakout_ENS160_BME280_QWIIC/arduino_examples/#example-1-ens160-and-bme280-combined-examples
#ifdef ENS160BME280_THING
#include <Wire.h>
#include "SparkFun_ENS160.h"  // Click here to get the library: http://librarymanager/All#SparkFun_ENS160
#include "SparkFunBME280.h"   // Click here to get the library: http://librarymanager/All#SparkFun_BME280

SparkFun_ENS160 myENS;
BME280 myBME280;
int ensStatus;

#endif

/**********************************************************************************************/
// functions executing THIS THING COMMANDS
// NOTE: functions must confirm to type f_commandExecutor (see theThing.hpp for details)
//
void restart_thing(TheThing* source, std::map<String, String> commandData, String sessionId, String respTopic){
  try {
    int32_t restartDelay = commandData["delay|ms|int"].toInt();
    DEBUGPRINTLN("Will restart after waiting for (ms): " + restartDelay);
    delay(restartDelay);
    ESP.restart();
  }
  catch(const std::exception& e) {
    DEBUGPRINTLN("Fail to execute restart command with error:");
    DEBUGPRINTLN(e.what());
  }
}
//
void set_measuring_interval(TheThing* source, std::map<String, String> commandData, String sessionId, String respTopic){
  try {
    int measuringInterval = std::strtoul(commandData["measuring-interval|min|int"].c_str(), nullptr, 0);
    source->setMeasuringInterval(measuringInterval);
    source->savePartOfTheModel(); // NOTE that after receiving this command attributes coded in defineThing will be ignored!
    DEBUGPRINTLN("Measuring interval (ms) updated to " + measuringInterval);
  }
  catch(const std::exception& e) {
    DEBUGPRINTLN("Fail to execute change measuring interval command with error:");
    DEBUGPRINTLN(e.what());
  }
}

/**********************************************************************************************/
// function executing THING collect DATA (must be of f_telemetryCollector type)
// NOTE that you can either provide this function or just overload collectData method
std::map<String, String> collect_my_data(std::vector<String> dataFields, String sessionId) {
  std::map<String, String> result={};
  String sep = ", ";
  String report = std::accumulate(dataFields.begin(), dataFields.end(), String(),
        [&sep](String &x, String &y) {
            return x.isEmpty()? y : x + sep + y;
        }
    );
  DEBUGPRINTLN("Collect my data for " + report);
#ifdef DHT22_THING
  //!NOTE This particular Thing is using DHT22 to measure temperature and humidity
  dht.begin();
#endif
#ifdef TMP102_THING
  temperature.startOneShotConversion();
#endif
#ifdef BME680_THING
  // Tell BME680 to begin measurement.
  unsigned long endTime = bme.beginReading();
  if (endTime == 0) {
    DEBUGPRINTLN(F("Failed to begin reading BME680"));
  }
  // we can add a delay for measurements to complete (some meaningful work can be done here)
  // endTime -= millis();
  // delay(endTime>0?endTime+10:0);
  //*NOTE There's no need to delay() until millis() >= endTime: 
  //  bme.endReading() takes care of that. It's okay for parallel work to take longer than BME680's measurement time.

  // Obtain measurement results from BME680. Note that this operation isn't
  // instantaneous even if milli() >= endTime due to I2C/SPI latency.
  if (!bme.endReading()) {
    DEBUGPRINTLN(F("FAILED to complete reading from BME680"));
  }
#endif
#ifdef ENS160BME280_THING
  // begin Wire
  if (!Wire.begin(21,22)) {
    DEBUGPRINTLN("I2C fails to begin.");
    return result;
  }
  // Tell BME280 to begin measurement.
  if (!myENS.begin(0x53)) {
    DEBUGPRINTLN("ENS fails to begin.");
    return result;
  }

  // Begin communication over I2C
  if (myBME280.beginI2C() == false) {
    DEBUGPRINTLN("BME280 sensor did not respond.");
    return result;
  }
  // we'll use bme280 data to compensate ens160 readings
  // see https://github.com/sparkfun/SparkFun_Indoor_Air_Quality_Sensor-ENS160_Arduino_Library/blob/main/examples/example4_BME280_temp_rh_compensation/example4_BME280_temp_rh_compensation.ino
  float relativeH = myBME280.readFloatHumidity();
  float temperatureC = myBME280.readTempC();

  // Reset the indoor air quality sensor's settings.
  if (myENS.setOperatingMode(SFE_ENS160_RESET))
    DEBUGPRINTLN("Ready.");
  delay(300);
  myENS.setTempCompensationCelsius(temperatureC);
  myENS.setRHCompensationFloat(relativeH);
  delay(500);

  // Device needs to be set to idle to apply any settings.
  // myENS.setOperatingMode(SFE_ENS160_IDLE);
  // delay(100);

  // Set to standard operation
  // Others include SFE_ENS160_DEEP_SLEEP and SFE_ENS160_IDLE
  myENS.setOperatingMode(SFE_ENS160_STANDARD);
  delay(100);

  // There are four values here:
  // 0 - Operating ok: Standard Operation
  // 1 - Warm-up: occurs for 3 minutes after power-on.
  // 2 - Initial Start-up: Occurs for the first hour of operation and only once in sensor's lifetime.
  // 3 - No Valid Output
  ensStatus = myENS.getFlags();
  Serial.print("Gas Sensor Status Flag: ");
  DEBUGPRINTLN(ensStatus);
  switch (ensStatus) {
  case 0:
    DEBUGPRINTLN("Operating ok: Standard Operation");
    break;
  case 1:
    DEBUGPRINTLN("Warm-up: occurs for 3 minutes after power-on.");
    break;
  case 2:
    DEBUGPRINTLN("Initial Start-up: Occurs for the first hour of operation and only once in sensor's lifetime.");
    break;
  case 3:
    DEBUGPRINTLN("No Valid Output");
    break;  
  default:
    DEBUGPRINTLN("Unexpected flag!!!");
    break;
  }

  // unsigned long endTime = bme.beginReading();
  // if (endTime == 0) {
  //   DEBUGPRINTLN(F("Failed to begin reading BME680"));
  // }
  // // we can add a delay for measurements to complete (some meaningful work can be done here)
  // // endTime -= millis();
  // // delay(endTime>0?endTime+10:0);
  // //*NOTE There's no need to delay() until millis() >= endTime: 
  // //  bme.endReading() takes care of that. It's okay for parallel work to take longer than BME680's measurement time.

  // // Obtain measurement results from BME680. Note that this operation isn't
  // // instantaneous even if milli() >= endTime due to I2C/SPI latency.
  // if (!bme.endReading()) {
  //   DEBUGPRINTLN(F("FAILED to complete reading from BME680"));
  // }
#endif

  for (String fieldName : dataFields) {
    DataPoint dp = TheThing::endpointFromId(fieldName);
    result[fieldName] = dp.pointDataType + " unavailable";
    if (dp.pointName=="chip" && dp.pointType==EndpointType.TEMPERATURE) {
      result[fieldName] = String(temperatureRead());
    } else {
      if (dp.pointName=="air") {
//! NOTE that this specific implementation presumes that we have just ONE sensor for "air" param
//! multiple sensors for the same param will result in value overwrite !
#ifdef TMP102_THING
        if (dp.pointType==EndpointType.TEMPERATURE) {
          int waited_ms = 0;
          while((!temperature.checkConversionReady()) && (waited_ms<3000)){
              waited_ms++;
              delay(1);
            }
          result[fieldName] = waited_ms<3000?String(temperature.readTemperatureC()):dp.pointDataType + " unavailable";
        } 
#endif
#ifdef DHT22_THING
        if (dp.pointType==EndpointType.TEMPERATURE) result[fieldName] = String(dht.readTemperature());
        else 
          if (dp.pointType==EndpointType.HUMIDITY) result[fieldName] = String(dht.readHumidity());
#endif
#ifdef BME680_THING
        if (dp.pointType==EndpointType.TEMPERATURESKEWED) result[fieldName] = String(bme.temperature);
        else 
          if (dp.pointType==EndpointType.HUMIDITY) result[fieldName] = String(bme.humidity);
          else
            if (dp.pointType==EndpointType.PRESSURE) result[fieldName] = String(bme.pressure / 100.0);
            else 
              if (dp.pointType==EndpointType.GASRESISTANCE) result[fieldName] = String(bme.gas_resistance / 1000.0);
#endif
#ifdef ENS160BME280_THING
/*
EndpointType.IAQ Serial.print("Air Quality Index (1-5) : "); Serial.println(myENS.getAQI());
EndpointType.BREATH_VOC Serial.print("Total Volatile Organic Compounds: "); Serial.print(myENS.getTVOC()); Serial.println("ppb");
EndpointType.CO2 Serial.print("CO2 concentration: "); Serial.print(myENS.getECO2()); Serial.println("ppm");
EndpointType.HUMIDITY Serial.print("Humidity: "); Serial.print(myBME280.readFloatHumidity(), 0); Serial.println("RH%");
EndpointType.PRESSURE Serial.print("Pressure: "); Serial.print(myBME280.readFloatPressure(), 0); Serial.println("Pa");
EndpointType.ALTITUDE Serial.print("Alt: "); Serial.print(myBME280.readFloatAltitudeMeters(), 1); Serial.println("meters");
EndpointType.TEMPERATURE Serial.print("Temp: "); Serial.print(myBME280.readTempC(), 2); Serial.println(" degC");
*/
        int waited_ms = 0;
        DEBUGPRINT("Wait for ENS data");
        while((!myENS.checkDataStatus()) && (waited_ms<30)){
            waited_ms++;
            delay(100);
            DEBUGPRINT(".");
        }
        if (myENS.checkDataStatus()) {
          DEBUGPRINTLN("");
        } else {
          DEBUGPRINTLN("WARNING ENS checkDataStatus returned FALSE");
        }
        if (dp.pointType==EndpointType.IAQ) result[fieldName] = String(myENS.getAQI());
        else 
          if (dp.pointType==EndpointType.BREATH_VOC) result[fieldName] = String(myENS.getTVOC());
          else 
            if (dp.pointType==EndpointType.CO2) result[fieldName] = String(myENS.getECO2());
        if (dp.pointType==EndpointType.TEMPERATURE) result[fieldName] = String(myBME280.readTempC());
        else 
          if (dp.pointType==EndpointType.HUMIDITY) result[fieldName] = String(myBME280.readFloatHumidity());
          else
            if (dp.pointType==EndpointType.PRESSURE) result[fieldName] = String(myBME280.readFloatPressure()/100);
            else 
              if (dp.pointType==EndpointType.ALTITUDE) result[fieldName] = String(myBME280.readFloatAltitudeMeters());
#endif
      } else {
        if (dp.pointName=="not air but something else") {
          // TBD
        }
      }
    }
    DEBUGPRINTLN("Value '"+result[fieldName]+"' collected for '"+fieldName+"'");
  }
  return result;
}

/**********************************************************************************************/
/**
 * *THIS IS AN ALTERNATIVE OPTION - derive your own Thing definition and have full flexibility
 * @brief describe MY THING - it's just a class derived from TheThing
 * @param {String} thingName
 * @param {String} thingGroup
 * @param {String} thingType
 * @param {String} thingBuildingId
 * @param {String} thingLocationId, 
 * @param {bool} [overwrite] default=true
 */ 
class OneThing : public TheThing {
  public:
    /**
     */
    using TheThing::TheThing; // we'll just use parent constructor

    /**
     * @brief In current implementation you have to provide your own collectStatusContent implementation here
     * 
     * @param contentType 
     */
    inline void collectStatusContent(String contentType) {

    };

    // You CAN overload collectData - take a look on implementation in theThing.hpp
    // using TheThing::collectData;
    // inline bool collectData() { };

    using TheThing::commandReceived;

    /**
     * @brief reloadable method to execute some "pre-deepsleep" actions
     */
    void preSleep( unsigned long sleepTime) {
#ifdef DHT22_THING
      // turn power off for sensor
      digitalWrite(DHTPOWERPIN, LOW);
#endif
#ifdef BME680_THING
    if (!bme.begin()) {
      DEBUGPRINTLN(F("Could not find a valid BME680 sensor, check wiring!"));
    }
    // Set up oversampling and filter initialization
    bme.setTemperatureOversampling(BME680_OS_8X);
    bme.setHumidityOversampling(BME680_OS_2X);
    bme.setPressureOversampling(BME680_OS_4X);
    bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
    bme.setGasHeater(320, 150); // 320*C for 150 ms    
#endif
#ifdef ENS160BME280_THING
    if (myENS.begin()) {
      // Set up oversampling and filter initialization
      myENS.setOperatingMode(SFE_ENS160_IDLE);
      delay(100);
      myENS.setOperatingMode(SFE_ENS160_DEEP_SLEEP);
      delay(100);
    } else {
      DEBUGPRINTLN(F("Could not find a valid ENS sensor, check wiring!"));
    }
#endif
    };

    /**
     * @brief You CAN overload the whole commandReceived if want a full control over command messages received
     * However the better approach will be to use addCommand method
     * @param commandPayload 
     * @param topic 
     */
    inline void commandReceived(String commandPayload, String topic) {
      DEBUGPRINT("Command received at topic ");
      DEBUGPRINTLN(topic);
      DEBUGPRINTLN("With payload:");
      DEBUGPRINTLN(commandPayload);
      // it is highly recommended to call overloaded method unless you know what you're doing
      TheThing::commandReceived(commandPayload, topic);
    }

    /**
     * @brief define this particular Thing
     * this can be done with method (like this),
     * or in main.cpp or as a separate function
     * 
     * @param serial 
     */
    inline void defineThing(String serial) {
      // this is an example of child-specific method
#ifdef TMP102_THING
      Wire.begin();
      temperature.enableShutdownMode();
#endif
#ifdef DHT22_THING
      // turn power on for sensor
      digitalWrite(DHTPOWERPIN, HIGH);
#endif
      // We'll add params and attribs if no Model data is available in NVS
      // This may seem complicated but attributes and properties may be updated from the backend
      if (!loadPartOfTheModel()) {
        // define top-level properties
        //* NOTE that combination of this two parameters makes possible regular measurements without deep sleep !!!
        setMeasuringInterval(15*60*1000); // Measure data every 15min
        unsigned long awakeTime = 15*1000; // Max awake is 15sec BY DEFAULT
#if defined(BME680_THING) || defined(ENS160BME280_THING)
        awakeTime = getMeasuringInterval() * 2; // no Sleep for BME680/280 !
#endif        
        setMaxAwakeTime(awakeTime);         
        // add attributes
        addAttribute("serial|hex|str", serial);
        // we will NOT store in the NVS as we may want to add more attributes in the code
        // savePartOfTheModel();
      }
      //--------------------------------------------------------------
      // add endpoints
      // AIR DATA
      addDataEndpoint("air", EndpointType.TEMPERATURE, "C", "float");
      // addDataEndpoint("air", EndpointType.TEMPERATURESKEWED, "C", "float");
      addDataEndpoint("air", EndpointType.HUMIDITY, "%", "float");
      addDataEndpoint("air", EndpointType.PRESSURE, "hPa", "float");
      // addDataEndpoint("air", EndpointType.GASRESISTANCE, "KOhms", "float");
      addDataEndpoint("air", EndpointType.IAQ, "1-5", "int");
      addDataEndpoint("air", EndpointType.CO2, "ppm", "int");
      addDataEndpoint("air", EndpointType.BREATH_VOC, "ppb", "int");
      addDataEndpoint("air", EndpointType.ALTITUDE, "m", "float");
      // BOARD DATA
      addDataEndpoint("chip", EndpointType.TEMPERATURE, "C", "float");
      //--------------------------------------------------------------
      // add commands and handler
      addCommand("restart", {"delay|ms|int"}, &restart_thing);
      addCommand("change-measuring-interval", {"measuring-interval|min|int"}, &set_measuring_interval);
      addCommand("change-maxawaketime", {"maxawaketime|min|int"}, &set_measuring_interval);
      //--------------------------------------------------------------
      // add status content types
      // addStatusContentType("", {});
      //--------------------------------------------------------------
      // add telemetry collector
      setTelemetryCollector(&collect_my_data);
    }
};

#endif