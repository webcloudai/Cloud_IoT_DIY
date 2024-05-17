/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#include "theThing.hpp"

// Thing Endpoint name convention
/** Convert endpoint to id*/
String TheThing::endpointId(String pointName, String pointType, String pointUnits, String pointDataType) {
  return pointName+"-"+pointType+"|"+pointUnits+"|"+pointDataType;
}
/** Convert id to the instance of DataPoint with respect to naming convention */
DataPoint TheThing::endpointFromId(String pointId) {
  DataPoint dp;
  unsigned int i=0;
  while(pointId.charAt(i) != '-') dp.pointName+=pointId[i++];
  unsigned int idPart = 0;
  for(++i; i < pointId.length(); i++){
    if(pointId.charAt(i) != '|') {
      switch (idPart) {
        case 0:
          dp.pointType+=pointId[i];
          break;
        case 1:
          dp.pointUnits+=pointId[i];
          break;
        case 2:
          dp.pointDataType+=pointId[i];
          break;
        default:
          DEBUGPRINT("ERROR when decoding pointId: ");
          DEBUGPRINTLN(pointId);
      }
    } else idPart++;
  }
  return dp;
}


/**
* Basic constructor which will collect all required values from NVS
*/
TheThing::TheThing() { updateFromNvs(); }

/*
* Constructor which will provide parameters instead of collecting them from the NVS
* Use with care - if provided parameters will be different from NVS - it'll trigger reprovisioning!
*/
TheThing::TheThing(
  String thingName, String thingGroup, String thingType, 
  String thingBuildingId, String thingLocationId, bool overwrite) {
    // collect properties from NVS first
    updateFromNvs();
    reprovision = false;
    if (minPropsAvailable() && !overwrite) return;
    reprovision = updateIfNeeded(thingName, thingGroup, thingType, thingBuildingId, thingLocationId, overwrite);
}
/**
 * Gracefully update current properties
*/
bool TheThing::updateIfNeeded(
  String thingName, String thingGroup, String thingType, 
  String thingBuildingId, String thingLocationId, bool overwrite) {
    bool updated = false;
    if(name.length()==0||((name!=thingName)&&overwrite)) {
      name = thingName;
      updated = true;
    }
    if(group.length()==0||((group!=thingGroup)&&overwrite)) {
      group = thingGroup;
      updated = true;
    }
    if(type.length()==0||((type!=thingType)&&overwrite)) {
      type = thingType;
      updated = true;
    }
    if(buildingId.length()==0||((buildingId!=thingBuildingId)&&overwrite)) {
      buildingId = thingBuildingId;
      updated = true;
    }
    if(locationId.length()==0||((locationId!=thingLocationId)&&overwrite)) {
      locationId = thingLocationId;
      updated = true;
    }
    if (updated) updateNvsFromProps();
    return updated;
}
/*
* Check if minimal properties (required for provisioning) are available
*/
bool TheThing::minPropsAvailable() {
  bool result = name.length()>0&&group.length()>0&&type.length()>0&&buildingId.length()>0&&locationId.length()>0;
  if (!result) {
    DEBUGPRINTLN("Not all Thing properties has been defined!");
    DEBUGPRINTLN(name);
    DEBUGPRINTLN(group);
    DEBUGPRINTLN(type);
    DEBUGPRINTLN(buildingId);
    DEBUGPRINTLN(locationId);
  }
  return result;
}
/*
* collect properties from NVS
*/
void TheThing::updateFromNvs() {
  /*******************************************************************/
  // define some values for Thing
  // Preferences lib for non-volatile data is used as we're using ESP32
  // For other microcontrollers you maybe need EEPROM lib
  /*******************************************************************/
  Preferences thingPersistentInfo;
  thingPersistentInfo.begin(THING_NAMESPACE, true);
  name = thingPersistentInfo.getString(THIS_THING_NAME, "");
  group = thingPersistentInfo.getString(THIS_THING_GROUP, "");
  type = thingPersistentInfo.getString(THIS_THING_TYPE, "");
  buildingId = thingPersistentInfo.getString(THIS_THING_BLDNG, "");
  locationId = thingPersistentInfo.getString(THIS_THING_LCTN, "");
  thingPersistentInfo.end();
}
/*
* write current properties to NVS
*/
void TheThing::updateNvsFromProps() {
  Preferences thingPersistentInfo;
  thingPersistentInfo.begin(THING_NAMESPACE, false);
  thingPersistentInfo.clear();
  thingPersistentInfo.putString(THIS_THING_NAME, name);
  thingPersistentInfo.putString(THIS_THING_GROUP, group);
  thingPersistentInfo.putString(THIS_THING_TYPE, type);
  thingPersistentInfo.putString(THIS_THING_BLDNG, buildingId);
  thingPersistentInfo.putString(THIS_THING_LCTN, locationId);
  thingPersistentInfo.end();
}
/*
* Clear all data from NVS Thing Namespace
*/
void TheThing::clearThingNvs() {
  Preferences thingPersistentInfo;
  thingPersistentInfo.begin(THING_NAMESPACE, false);
  thingPersistentInfo.clear();
  thingPersistentInfo.end();
}
/**
 * @brief save attributes and Model top-level props to NVS
 * 
 */
void TheThing::savePartOfTheModel() {
  Preferences modelPersistentInfo;
  modelPersistentInfo.begin(MODEL_NAMESPACE, false);
  modelPersistentInfo.clear();
  modelPersistentInfo.putString(MODEL_ATTRIB, attributesToJsonString());
  modelPersistentInfo.putLong64(MODEL_INTERVAL, model.measuringInterval);
  modelPersistentInfo.putLong64(MODEL_AWAKE, model.maxAwakeTime);
  modelPersistentInfo.end();
}
/**
 * @brief load attributes and Model top-level props from NVS
 * 
 */
bool TheThing::loadPartOfTheModel() {
  Preferences modelPersistentInfo;
  modelPersistentInfo.begin(MODEL_NAMESPACE, true);
  unsigned long mInterval = 0;
  unsigned long mAwake = 0;
  String attribs = "{}";
  try {
    mInterval = modelPersistentInfo.getLong64(MODEL_INTERVAL, model.measuringInterval);
    mAwake = modelPersistentInfo.getLong64(MODEL_AWAKE, model.maxAwakeTime);
    attribs = modelPersistentInfo.getString(MODEL_ATTRIB, attributesToJsonString());
    // we need to deserialize collected String into the object
    // we need quite large buffer as attributes can contain multiple values
    // This buffer is actually limit Model Attributes size to 4Kb
    StaticJsonDocument<4096> attribDeserialized;
    // Deserialize the JSON document
    DeserializationError deserError = deserializeJson(attribDeserialized, attribs);
    // Test if parsing succeeds.
    if (deserError) {
        DEBUGPRINT("TheThing::loadPartOfTheModel FAIL to load Model with error ");
        DEBUGPRINTLN(deserError.f_str());
        return false;
    }
    // Fill up attributes from deserialized JSON document.
    JsonObject attribDeserializedData = attribDeserialized.to<JsonObject>();
    for (JsonPair kv : attribDeserializedData) {
        String cKey = String(kv.key().c_str());
        String cValue = String(kv.value().as<const char*>());
        model.attributes[cKey] = cValue;
    }
    model.maxAwakeTime = mAwake;
    model.measuringInterval = mInterval;
  } catch(const std::exception& e) {
    DEBUGPRINTLN("TheThing::loadPartOfTheModel FAIL to load Model with error "+String(e.what()));
    return false;
  }    
  modelPersistentInfo.end();
  return true;
}


/*
* Put Thing to deep sleep until next measurement needed
*/
void TheThing::goSleep() { 
  for (int devDebugDelay=0; devDebugDelay<60; devDebugDelay++) {
    for (int i=0; i<6; i++) { 
      CHANGE_STATUS_LED(); 
      delay(100); 
    }
    delay(1500);
  }
  unsigned long sleepTime = model.measuringInterval-millis();
  if (model.measuringInterval>(millis()+1000)) {
    DEBUGPRINT("Will sleep for (ms): ");
    DEBUGPRINTLN(sleepTime);
    preSleep(sleepTime);
    ESP.deepSleep((model.measuringInterval-millis())*1000); //! deepSleep interval is in MICROseconds !
  }
}
/*
* this actually set's up Sleep Interval
* it's expected that Thing will sleep between 
*/
void TheThing::setMeasuringInterval(unsigned long intervalMs) {model.measuringInterval=intervalMs;};
/*
* add attribute reflecting some Thing static property
* @example addAttribute("serial", <device MAC>)
*/
void TheThing::addAttribute(String attrName, String attrValue) {model.attributes[attrName]=attrValue;};
/*
* add information about data endpoint (sensor)
* naming convention for the MQTT data field implemented with endpointId
* @return endpoint id which is MQTT data field name
* @example addDataEndpoint("air", EndpointType.TEMPERATURE, "C", "float")
*/
String TheThing::addDataEndpoint(String pointName, String pointType, String pointUnits, String pointDataType) {
  String pointId = endpointId(pointName,pointType,pointUnits,pointDataType);
  model.dataFieldNames.push_back(pointId);
  return pointId;
};
    
/**
* this just assign the function to be called for telemetry data collection
*/
void TheThing::setTelemetryCollector(f_telemetryCollector dataCollector) {telemetryCollector=dataCollector;};
/**
* add information about commands (device actions)
* @example addCommand("restart", {"delay|ms|int"}, &<executor function>)
* @example addCommand("change measuring interval", {"measuring-interval|min|int"}, &<executor function>)
*/
void TheThing::addCommand(String cmdName, std::vector<String> cmdDataFields, f_commandExecutor f_executor) {
  cmdExecutorsByCommand[cmdName] = f_executor;
  model.cmdFieldsByCommand[cmdName]=cmdDataFields;
};
/**
* add information about status content (device status and other device-to-cloud messages)
* NOTE: you don't need to define standard "update model" - that will be implemented by backend connection!
*/
void TheThing::addStatusContentType(String contentType, std::vector<String> contentDataFields) {
  model.statusFieldsByType[contentType]=contentDataFields;
};
/*
* Returns Model of this Thing.
* Is used by BackendConnection to push Model to Cloud
*/
ThingModel TheThing::thingModel() { return model; }

/**
 * Returns String description of the Thing Data Fields (model.dataFieldNames)
*/
String TheThing::describeDataFields(String sep) {
  String report = std::accumulate(model.dataFieldNames.begin(), model.dataFieldNames.end(), String(),
        [&sep](String &x, String &y) {
            return x.isEmpty()? ("\""+y+"\"") : x + sep + ("\""+y+"\"");
        }
  );
  return "[" + report + "]";
}
/**
 * Returns String description of the Thing Commands (model.cmdFieldsByCommand keys)
*/
String TheThing::describeCommands(String sep) {
  String report = std::accumulate(model.cmdFieldsByCommand.begin(), model.cmdFieldsByCommand.end(), String(),
      [&sep](String &x, const std::pair<String, std::vector<String>> &p) {
            String cmdFields = std::accumulate(p.second.begin(), p.second.end(), String(),
              [&sep](String &xx, const String &yy) {
                return xx.isEmpty()? ("\""+yy+"\"") : xx + sep + ("\""+yy+"\"");
              }
            );
            String elemDescr = "\""+p.first+"\":[" + cmdFields + "]";
            return x.isEmpty()? elemDescr : x + sep + elemDescr;
        }
  );
  // return "[" + (report.length()>sep.length())?report.substring(0,report.length()-sep.length()):report + "]";
  return "{" + report + "}";
}
/**
 * Returns String description of the Thing Status Types (model.statusFieldsByType keys)
*/
String TheThing::describeStatusTypes(String sep) {
  String report = std::accumulate(model.statusFieldsByType.begin(), model.statusFieldsByType.end(), String(),
      [&sep](String &x, const std::pair<String, std::vector<String>> &p) {
            String stFields = std::accumulate(p.second.begin(), p.second.end(), String(),
              [&sep](String &xx, const String &yy) {
                return xx.isEmpty()? ("\""+yy+"\"") : xx + sep + ("\""+yy+"\"");
              }
            );
            String elemDescr = "\""+p.first+"\":[" + stFields + "]";
            return x.isEmpty()? elemDescr : x + sep + elemDescr;
        }
  );
  return "{" + report + "}";
}
/**
 * Returns JSON String with description of the Thing properties
*/
String TheThing::propertiesToJsonString() {
  String report = "{ ";
  report += "\"name\":\""+name+"\",";
  report += "\"group\":\""+group+"\",";
  report += "\"type\":\""+type+"\",";
  report += "\"buildingId\":\""+buildingId+"\",";
  report += "\"locationId\":\""+locationId+"\"";
  return report +" }";
}
/**
 * Returns JSON String with Thing attributes (model.attributes keys and values)
*/
String TheThing::attributesToJsonString() {
  String sep = ", ";
  String report = std::accumulate( model.attributes.begin(), model.attributes.end(), String(),
      [&sep](String &x, const std::pair<String, String> &p) {
          String elemDescr = "\"" + p.first + "\": \"" + p.second + "\"";
          return x.isEmpty() ? elemDescr:x+sep+elemDescr;
        }
  );
  return "{ " + report +" }";
}
/**
 * Returns JSON String with whole Thing model
*/
String TheThing::modelToJsonString() {
  String report = "{ ";
  report += "\"measuringInterval|ms|int\":\""+String(model.measuringInterval)+"\",";
  report += "\"maxAwakeTime|ms|int\":\""+String(model.maxAwakeTime)+"\",";
  report += "\"attributes\":" + attributesToJsonString() + ",";
  report += "\"dataFieldNames\":" + describeDataFields(",") + ",";
  report += "\"cmdFieldsByCommand\":" + describeCommands(",") + ",";
  report += "\"statusFieldsByType\":" + describeStatusTypes(",");
  return report +" }";
}
/**
 * Returns JSON String with whole Thing definition
*/
String TheThing::thingToJsonString() {
  String report = "{ ";
  report += "\"properties\":" + propertiesToJsonString() + ",";
  report += "\"model\":" + modelToJsonString();
  return report +" }";
}
/**
 * @brief Things definition has multiple "angles" and thingToJsonString() method helps to describe it
 * this method creates hash of that description which helps to control if thing was changed 
 * 
 * @return String 
 */
String TheThing::thingDefinitionHash() {
  // thanks to https://stackoverflow.com/questions/8317508/hash-function-for-a-string
  String thingDescription = thingToJsonString();
  unsigned long hash = 37;
  for (int i=0; i<thingDescription.length(); i++) 
    hash = (hash * 54059) ^ (thingDescription[i] * 76963);
  hash = hash % 86969;
  return String(hash);
}

/**
* This method will be invoked when command received from the backend
* NOTE that it can be command or response to your status message
*/
void TheThing::commandReceived(String messagePayload, String topic) {
  DEBUGPRINT("Command received at topic ");
  DEBUGPRINTLN(topic);
  DEBUGPRINTLN("With payload:");
  DEBUGPRINTLN(messagePayload);
  // 1. Deserialize payload
  StaticJsonDocument<8192> commandPayload;
  // Deserialize the JSON document
  DeserializationError deserError = deserializeJson(commandPayload, messagePayload);
  // Test if parsing succeeds.
  if (deserError) {
      DEBUGPRINT("TheThing::commandReceived FAIL to deserialize message with error ");
      DEBUGPRINTLN(deserError.f_str());
      return;
  }
  // 2. Identify command
  if (!commandPayload.containsKey("command")) {
    DEBUGPRINTLN("TheThing::commandReceived no command found");
    return;
  }
  String command = commandPayload["command"].as<String>();
  // 3. Check if command is supported
  if (model.cmdFieldsByCommand.find(command)==model.cmdFieldsByCommand.end() ||
      cmdExecutorsByCommand.find(command)==cmdExecutorsByCommand.end()) {
    DEBUGPRINTLN("TheThing::commandReceived command "+command+" is not supported");
    return;
  }
  // 4. Collect command parameters
  String sessionId = commandPayload.containsKey("session-id")?commandPayload["session-id"].as<String>():"";
  String respTopic = commandPayload.containsKey("resp-topic")?commandPayload["resp-topic"].as<String>():"";
  std::map<String, String> commandData={};
  if (commandPayload.containsKey("data")) {
    try {
      JsonObject commandMessageData = commandPayload["data"].to<JsonObject>();
      for (JsonPair kv : commandMessageData) {
          String cKey = String(kv.key().c_str());
          String cValue = String(kv.value().as<const char*>());
          commandData[cKey] = cValue;
      }		
    } catch(const std::exception& e) {
      DEBUGPRINTLN("TheThing::commandReceived FAIL to deserialize command data with error "+String(e.what()));
      return;
    }    
  }
  // 5. Invoke command executor
  try {
    cmdExecutorsByCommand[command](this, commandData, sessionId, respTopic);
  } catch(const std::exception& e) {
      DEBUGPRINTLN("TheThing::commandReceived FAILURE when executing command with error "+String(e.what()));
      return;
  }
}
    
/**
* This method MUST COLLECT DATA FROM SENSORS AND FILL UP readingsData property
* keys are DataEndpoint IDs (values from dataFieldNames)
* values are collected data converted to String !!!
*/
bool TheThing::collectData(String sessionId) {
  readingsData = telemetryCollector(model.dataFieldNames, sessionId); 
  return true;
}
/**
 * Getter for protected readingsData
*/
std::map<String, String> TheThing::latestData() { return readingsData; }
/**
 * Collect readingData as JSON string
*/
String TheThing::latestDataToJsonString() {
  String sep = ", ";
  String report = std::accumulate( readingsData.begin(), readingsData.end(), String(),
      [&sep](String &x, const std::pair<String, String> &p) {
          String elemDescr = "\"" + p.first + "\": \"" + p.second + "\"";
          return x.isEmpty() ? elemDescr:x+sep+elemDescr;
            // return x + "\"" + p.first + "\": \"" + p.second + "\"" + sep;
        }
  );
  return "{ " + report +" }";
}
