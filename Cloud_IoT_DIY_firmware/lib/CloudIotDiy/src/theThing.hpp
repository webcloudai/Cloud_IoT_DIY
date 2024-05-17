/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#ifndef THE_THING_ABSTRACT
#define THE_THING_ABSTRACT

#include <vector>
#include <map>
#include <numeric>
#include <Arduino.h>
#include <Preferences.h>
#include <ArduinoJson.h>

#include "configHardwareConstants.hpp"
#include "_projectData.hpp"

// predefined Endpoint Types
const struct  {
  String TEMPERATURE = "temperature";
  String TEMPERATURESKEWED = "temperatureSkewed";
  String PRESSURE = "pressure";
  String HUMIDITY = "humidity";
  String GASRESISTANCE = "gasResistance";
  String IAQ = "iaq";
  String CO2 = "co2";
  String BREATH_VOC = "breathVoc";
  String ALTITUDE = "altitude";
} EndpointType;

/****************************************************************************/
/************************* Thing Model definition ***************************/
struct ThingModel{
  /** interval between measurements in ms (thing will go deep sleep) */
  unsigned long measuringInterval = 15*60*1000;
  /** the thing will remain awake even when telemetry collected and sent
      to collect potential data from the cloud
      this value defines for how long the thing will be awake after completing setup */
  unsigned long maxAwakeTime = 15*1000;
  /** supported attributes (static properties like serial number) */
  std::map<String,String> attributes={};
  /** data field name for particular thing */
  std::vector<String> dataFieldNames=std::vector<String>(0);
  /** Field names for command 'data' section. Per command name */
  std::map<String, std::vector<String>> cmdFieldsByCommand={};
  /** Field names for static 'data' section. Per status type */
  std::map<String, std::vector<String>> statusFieldsByType={};
};

// defines one particular data endpoint parameters
class DataPoint {
  public:
    String pointName="";
    String pointType="";
    String pointUnits="";
    String pointDataType="";
};

/****************************************************************************/
/************************ TheThing abstract class ***************************/
// declare first to resolve circular reference between class and executor type
class TheThing;
// Define type for Command Executor functions
typedef void (*f_commandExecutor)(TheThing* source, std::map<String, String> commandData, String sessionId, String respTopic);
// Define type for Data Collection function
typedef std::map<String, String> (*f_telemetryCollector)(std::vector<String> dataFields, String sessionId);

/*
* Define your own Thing by inheriting from this abstract class and
* - implementing collectData and collectStatusContent
* - defining your Thing model either wit add* methods or by providing init values
*/
class TheThing {
  private:
    const char* THING_NAMESPACE = "THING";      // nvs namespace for this Thing data
    const char* THIS_THING_NAME = "THINGNAME";  // key for thing name in the THING namespace
    const char* THIS_THING_GROUP = "THINGGROUP";  // key for thing group in the THING namespace
    const char* THIS_THING_TYPE = "THINGTYPE";  // key for thing type in the THING namespace
    const char* THIS_THING_BLDNG = "THINGBLDNG";// key for thing building id in the THING namespace
    const char* THIS_THING_LCTN = "THINGLCTN";  // key for thing location id in the THING namespace

    const char* MODEL_NAMESPACE = "THING";      // nvs namespace for this Model data
    const char* MODEL_ATTRIB = "MODELATTRIB";   // key for thing ATTRIBUTES in the MODEL namespace
    const char* MODEL_INTERVAL = "MODELINTERVAL"; // key for thing measuringInterval in the MODEL namespace
    const char* MODEL_AWAKE = "MODELAWAKE";     // key for thing maxAwakeTime in the MODEL namespace

  protected:
    /*************************************************************/
    /********************* Model definitions *********************/
    ThingModel model;

    /* Mapping command names to external function implementing that command */
    std::map<String, f_commandExecutor> cmdExecutorsByCommand={};

    /*************************************************************/
    /*********** Data structures for current operation ***********/
    /**
    * readingsData to be filled up with sensors reading data
    * keys should be from dataFieldNames
    */
    std::map<String, String> readingsData={};
    /**
    * reference to telemetry collector may be provided
    */
    f_telemetryCollector telemetryCollector=NULL;
    /**
    * statusData to be filled up with information for specific contentType
    * keys should be from statusFieldsByType[contentType]
    */
    std::map<String, String> statusData={};

  public:

    // Thing Endpoint name convention
    /** Convert endpoint to id*/
    static String endpointId(String pointName, String pointType, String pointUnits, String pointDataType);
    /** Convert id to the instance of DataPoint with respect to naming convention */
    static DataPoint endpointFromId(String pointId);
    /**
     * This set of five properties are MINIMAL required for Thing to operate in the project
    */
    String name;
    String group;
    String type;
    String buildingId;
    String locationId;
    // special property to flag if Thing REPROVISIONING is required
    bool reprovision=false;

    /*******************************************/
    /*********** Thing instantiation ***********/
    /**
    * Basic constructor which will collect all required values from NVS
    */
    TheThing();
    /**
    * Constructor which will provide parameters instead of collecting them from the NVS
    * Use with care - if provided parameters will be different from NVS - it'll trigger reprovisioning!
    */
    TheThing(
      String thingName, String thingGroup, String thingType, 
      String thingBuildingId, String thingLocationId, bool overwrite=true);
    /*
    * Check if minimal properties (required for provisioning) are available
    */
    bool minPropsAvailable();

    /********************************************/
    /*********** Thing NVS operations ***********/
    /**
     * Gracefully update current properties
    */
    bool updateIfNeeded(
      String thingName, String thingGroup, String thingType, 
      String thingBuildingId, String thingLocationId, bool overwrite=true);
    /*
    * collect properties from NVS
    */
    void updateFromNvs();
    /*
    * write current properties to NVS
    */
    void updateNvsFromProps();
    /*
    * Clear all data from NVS Thing Namespace
    */
    void clearThingNvs();
    /**
     * @brief save attributes and Model top-level props to NVS
     * 
     */
    void savePartOfTheModel();
    /**
     * @brief load attributes and Model top-level props from NVS
     * 
     */
    bool loadPartOfTheModel();

    /********************************************/
    /*********** Thing configuration  ***********/
    /**
    * it's expected that Thing will sleep in between 
    */
    inline unsigned long getMaxAwakeTime() { return model.maxAwakeTime; }
    /**
    * it's expected that Thing will sleep for this time till next telemetry collection 
    */
    inline unsigned long getMeasuringInterval() { return model.measuringInterval; }
    /**
    * this actually set's up Sleep Interval
    * it's expected that Thing will sleep between 
    */
    void setMeasuringInterval(unsigned long intervalMs);
    /**
    * this actually set's up Max Awake time
    * it's expected that Thing will sleep after that 
    */
    inline void setMaxAwakeTime(unsigned long awakeTime) { model.maxAwakeTime = awakeTime;}
    /**
    * add attribute reflecting some Thing static property
    * @example addAttribute("serial", <device MAC>)
    */
    void addAttribute(String attrName, String attrValue);
    /**
    * add information about data endpoint (sensor)
    * naming convention for the MQTT data field implemented with endpointId
    * @return endpoint id which is MQTT data field name
    * @example addDataEndpoint("air", EndpointType.TEMPERATURE, "C", "float")
    */
    String addDataEndpoint(String pointName, String pointType, String pointUnits, String pointDataType);
    
    /**
    * this just assign the function to be called for telemetry data collection
    */
    void setTelemetryCollector(f_telemetryCollector dataCollector);
    /**
    * add information about commands (device actions)
    * @example addCommand("restart", {"delay|ms|int"}, &<executor function>)
    * @example addCommand("change measuring interval", {"measuring-interval|min|int"}, &<executor function>)
    */
    void addCommand(String cmdName, std::vector<String> cmdDataFields, f_commandExecutor f_executor);
    /**
    * add information about status content (device status and other device-to-cloud messages)
    * NOTE: you don't need to define standard "update model" - that will be implemented by backend connection!
    */
    void addStatusContentType(String contentType, std::vector<String> contentDataFields);
    /**
     * @brief Things definition has multiple "angles" and thingToJsonString() method helps to describe it
     * this method creates hash of that description which helps to control if thing was changed 
     * 
     * @return String 
     */
    String thingDefinitionHash();

    /********************************************/
    /***********  Thing DESCRIPTIONS  ***********/
    /**
    * Returns Model of this Thing.
    * Is used by BackendConnection to push Model to Cloud
    */
    ThingModel thingModel();
    /**
     * Returns String description of the Thing Data Fields (model.dataFieldNames)
    */
    String describeDataFields(String sep = ", ");
    /**
     * Returns String description of the Thing Commands (model.cmdFieldsByCommand keys)
    */
    String describeCommands(String sep = ", ");
    /**
     * Returns String description of the Thing Status Types (model.statusFieldsByType keys)
    */
    String describeStatusTypes(String sep = ", ");
    /**
     * Returns JSON String with description of the Thing properties
    */
    String propertiesToJsonString();
    /**
     * Returns JSON String with Thing attributes (model.attributes keys and values)
    */
    String attributesToJsonString();
    /**
     * Returns JSON String with whole Thing model
    */
    String modelToJsonString();
    /**
     * Returns JSON String with whole Thing definition
    */
    String thingToJsonString();

    /******************************************/
    /***********  Thing OPERATIONS  ***********/
    /**
    * Put Thing to deep sleep until next measurement needed
    */
    void goSleep();
    /**
     * @brief reloadable method to execute some "pre-deepsleep" actions
     */
    void preSleep( unsigned long sleepTime) {};
    /**
    * This method will be invoked when command received from the backend
    * NOTE that it can be command or response to your status message
    */
    void commandReceived(String messagePayload, String topic);
    
    /**
    * This method MUST COLLECT DATA FROM SENSORS AND FILL UP readingsData property
    * keys are DataEndpoint IDs (values from dataFieldNames)
    * values are collected data converted to String !!!
    */
    bool collectData(String sessionId="");
    /**
     * Getter for protected readingsData
    */
    std::map<String, String> latestData();
    /**
     * Collect readingData as JSON string
    */
    String latestDataToJsonString();
    
    /*****************************************************************/
    /************* V I R T U A L  M E T H O D S **********************/
    /*** T O  B E  I M P L E M E N T E D  F O R  A N Y  T H I N G ****/
    /**
    * This method MUST COLLECT DATA FOR PARTICULAR contentType AND FILL UP readingsData property
    * keys are DataEndpoint IDs (values from statusFieldsByType[contentType])
    * values are collected data converted to String !!!
    */
    virtual void collectStatusContent(String contentType) = 0;
};

#endif