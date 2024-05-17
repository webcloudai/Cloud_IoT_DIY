/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/
#ifndef ThingConfigClass
#define ThingConfigClass

#include <Arduino.h>

class ThingConfig {
    /*****************************************************************/
    /************* V I R T U A L  M E T H O D S **********************/
    /*** T O  B E  I M P L E M E N T E D  F O R  A N Y  T H I N G  C O N F I G ****/

    // Collect value from provided data. Only complete form data will be returned when partial is false
    virtual String valueFor(String paramName, bool partial=true, String defaultValue="")=0;

};

#endif