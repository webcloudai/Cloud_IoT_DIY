/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
#ifndef HTML_FORM_BASIC
#define HTML_FORM_BASIC

#include <vector>
#include <map>
#include <Arduino.h>
#include <AsyncTCP.h>
#include "ESPAsyncWebServer.h"
#include "thingConfig.hpp"
#include "_projectData.hpp"

/*
* Singleton class to handle HTML form
*/
class HtmlFormBasic : public ThingConfig {
  // public:
  private:
    // template parameters to be defined in the constructor
    static String formTitle;
    static String myLines;
    static String actionPath;
    static String actionMethod;
    // fields will be added by addParameter method
    // static String formFields[];
    static std::vector<String> formFields;
    // data to be filled when form submitted
    // static String fieldValues[];
    static std::vector<String> submittedData;
    // data to be filled with key from form and values from POST
    static std::map<String, String> submittedForm;

    // Define form template to be hosted on the Thing for backend configuration
    static const char* formTemplate;

    static String templateFill(const String& templateElement);

  public:
    // static String formTitle; // it maybe reasonable to make it public if we'll want to update it in th process
    static void formRequestHandler(AsyncWebServerRequest *request);
    static void formSubmitHandler(AsyncWebServerRequest *request);
    // Collect value for provided form. Only complete form data will be returned when partial is false
    // static String valueFor(String paramName, bool partial=true);
    static const char* formSubmitPath();
    
    /*
    * @param formSubmitPath - the path of the form POST request
    */
    HtmlFormBasic(String formSubmitPath, String title="Thing Configuration Form");

    void addParameter(String paramLabel, String paramId, String paramName, String paramType, String paramHint, String defaultValue="");
    // String renderForm() {
    //   return String();
    // }

    // Collect value from provided data. Only complete form data will be returned when partial is false
    String valueFor(String paramName, bool partial=true, String defaultValue="");


};

#endif