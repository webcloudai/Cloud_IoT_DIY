/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
#include "HtmlFormBasic.hpp"

// temp solution as configHardwareConstants is not included
#ifndef LOG_STACK_SIZE
// #define LOG_STACK_SIZE
#endif

#ifdef LOG_STACK_SIZE
void * StackPtrAtTheStart;
void * StackPtrTheEnd;
UBaseType_t watermarkAtStart;
#endif

// These static properties will be redefined in the constructor
String HtmlFormBasic::myLines = "";
String HtmlFormBasic::actionPath = "";
String HtmlFormBasic::actionMethod = "";
String HtmlFormBasic::formTitle = "Thing Configuration Form";
// fields will be added by addParameter method
// String HtmlFormBasic::formFields[] = {};
std::vector<String> HtmlFormBasic::formFields = std::vector<String>(0);
// submittedData will be filled up when on POST form
// String HtmlFormBasic::submittedData[] = {};
std::vector<String> HtmlFormBasic::submittedData = std::vector<String>(0);
// submittedForm will be filled up when on POST request
std::map<String, String> HtmlFormBasic::submittedForm = {};


// Define form template to be hosted on the Thing for backend configuration
const char* HtmlFormBasic::formTemplate = R"rawliteral(
<!DOCTYPE HTML><html><head><title>"%FORMTITLE%"</title><meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <style>
    form { margin: 0 auto; width: 400px; padding: 1em; border: 1px solid #ccc; border-radius: 1em; }
    ul { list-style: none; padding: 0; margin: 0; }
    form li + li { margin-top: 1em; }
    label { display: inline-block; width: 90px; text-align: right; }
    input,
    textarea { font: 1em sans-serif; width: 300px; box-sizing: border-box; border: 1px solid #999; }
    input:focus,
    textarea:focus { border-color: #000; }
    textarea { vertical-align: top; height: 5em; } 
    .button { padding-left: 90px; }
    button { margin-left: 0.5em; }
  </style>
</head>
<body> <h2>%FORMTITLE%</h2>
    <form action="%FORMACTIONPATH%" method="%FORMACTIONMETHOD%">
      <ul> %CONFIGURATIONFORM% 
        <li class="button"> <button type="submit">Submit configuration</button>
        </li>
      </ul>
    </form>
</body>
</html>
)rawliteral";

/*
* Static method to handle template updates with ESPAsyncWebServer
*/
String HtmlFormBasic::templateFill(const String& templateElement) {
  if (templateElement=="FORMTITLE") return HtmlFormBasic::formTitle;
  if (templateElement=="CONFIGURATIONFORM") return myLines;
  if (templateElement== "FORMACTIONPATH") return actionPath;
  if (templateElement== "FORMACTIONMETHOD") return actionMethod;
  return String();
}
/*
* Static method to support ESPAsyncWebServer form request
*/
void HtmlFormBasic::formRequestHandler(AsyncWebServerRequest *request){
  request->send_P(200, "text/html", formTemplate, templateFill);
}
/*
* Static method to support ESPAsyncWebServer form submit
* NOTE that expected method is POST
* and payload is ThingName=Name&ThingGroup=diyiot&ThingType=DiyThing&ThingBuilding=BuildingID...
*/
void HtmlFormBasic::formSubmitHandler(AsyncWebServerRequest *request){
#ifdef LOG_STACK_SIZE
    void* SpStart = NULL;
    StackPtrAtTheStart = (void *)&SpStart;
    watermarkAtStart =  uxTaskGetStackHighWaterMark(NULL);
    StackPtrTheEnd = StackPtrAtTheStart - watermarkAtStart;  
    Serial.printf("Free Stack near formSubmitHandler start is:  %d \r\n",  (uint32_t)StackPtrAtTheStart - (uint32_t)StackPtrTheEnd);
#endif
  submittedData.clear();
  submittedForm.clear();
  // String message="{\n";
  String shortValue="";
  String formValue = "";
  for (String fName : formFields) {
    if (request->hasParam(fName, true)) {
      try {
        formValue = request->getParam(fName, true)->value();
      } 
      catch(const std::exception& e) {
        DEBUGPRINT("FAIL to get form value for");
        DEBUGPRINTLN(fName);
        DEBUGPRINT("with exception");
        DEBUGPRINTLN(e.what());
        continue;
      }
      submittedData.push_back(formValue);
      submittedForm[fName] = formValue;
      shortValue = formValue.substring(0, min(int(formValue.length()),30));
      // if (message.length()>2)
      //   message += ",\n";
      // message += ("\"" + fName + "\": \"" + shortValue + "\"");
      DEBUGPRINT("Get form data: ");
      DEBUGPRINT(fName);
      DEBUGPRINT("=");
      DEBUGPRINTLN(shortValue);
    }
  }
  // message += "\n}";
  // if (message.length()>4) {
  //     message = "{\"ERROR\": \"No message sent\"}";
  // }
  try {
    // request->send(200, "text/plain", "Received data:\n" + message);
    if (request != NULL) {
      request->send(200, "text/plain", "Data received");
      DEBUGPRINTLN("Response with data received sent");
    } else DEBUGPRINTLN("FAIL - request is a NULL pointer!");
  }
  catch(const std::exception& e) {
      DEBUGPRINTLN("FAIL to response with data received sent");
      DEBUGPRINTLN(e.what());
  }
  // delay(500);
}
/**
 * @brief 
 * 
 * @param paramName 
 * @param partial 
 * @param defaultValue 
 * @return String 
 */
String HtmlFormBasic::valueFor(String paramName, bool partial, String defaultValue) {
  if (!partial && (submittedData.size() != formFields.size())) {
    DEBUGPRINTLN("Form data not all available yet "+String(submittedData.size())+"!="+ String(formFields.size()));
    return "";
  }
  if (partial) {
    if (submittedForm.find(paramName)==submittedForm.end()) {
      // no key found
      return defaultValue;
    } else {
      return submittedForm[paramName];
    }
  }
  int i=0; 
  for (String fName : formFields) {
    if (paramName==fName) return submittedData[i];
    i++;
  }
  return "";
}
/**
 * @brief 
 * 
 * @return const char* 
 */
const char* HtmlFormBasic::formSubmitPath() {
  return (const char*)(actionPath.c_str());
}
/*
* Class constructor
*/
HtmlFormBasic::HtmlFormBasic(String formSubmitPath, String title) {
  // we'll initializing STATIC class members here
  HtmlFormBasic::formTitle = title;
  actionPath = formSubmitPath;
  actionMethod = "post";
  myLines = "";
}

/*
* class instance configuration (however this method will update static properties)
* build standard form line of format
*  <li>
*    <label for=\"paramId\">
*      paramLabel 
*    </label>
*      <input type=\"paramType\" id=\"paramId\" name=\"paramName\" placeholder=\"paramHint\">
*  </li>
*/
void HtmlFormBasic::addParameter(String paramLabel, String paramId, String paramName, String paramType, String paramHint, String defaultValue) {
  String oneLine = "<li><label for=\"" + paramId + "\">" + paramLabel + "</label>";
  oneLine += "<input type=\""+paramType+"\" id=\""+paramId+"\" name=\""+paramName+"\" placeholder=\""+paramHint;
  if (defaultValue=="") {
    oneLine += "\"></li>";
  } else {
    oneLine += "\" value=\"" + defaultValue + "\"></li>";
  }
  myLines += oneLine;
  formFields.push_back(paramName);
}
