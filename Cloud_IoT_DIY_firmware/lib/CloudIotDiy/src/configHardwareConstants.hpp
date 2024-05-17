/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
*/

#ifndef HARDWARE_CONSTANTS
#define HARDWARE_CONSTANTS

// uncomment next line to enable STACK SIZE logging
// this can be extremely effective way to configure stack size in main.cpp
// #define LOG_STACK_SIZE


#include "Arduino.h"
// define some hardware params
const int BUTTON_PIN = 0;
const int STATUS_LED_PIN = 13;
#define CHANGE_STATUS_LED() digitalRead(STATUS_LED_PIN)==HIGH?digitalWrite(STATUS_LED_PIN, LOW):digitalWrite(STATUS_LED_PIN, HIGH)
/**
 * THIS IS IMPORTANT ! This statement loads LARGE CERTIFICATES BUNDLE
 * Which helps to use WiFiClientSecure with https to almost any endpoint
 * However if this is too large - you can remove it and create your own limited bundle
*/
extern const uint8_t rootca_crt_bundle_start[] asm("_binary_data_cert_x509_crt_bundle_bin_start");

/**
 * @brief 
 * 
 */
class BaseHardware {
    private:
        static const int RGBLED_BRIGHTNESS = 128; // Change white brightness (max 255) default is RGB_BRIGHTNESS
        static inline bool is_rgb_led_on() {
            BaseHardware::IS_RGB_LED_ON = !IS_RGB_LED_ON;
            return !IS_RGB_LED_ON;
        }
    public:
        static bool IS_RGB_LED_ON;
        static inline void TURN_RGBLED_OFF() { neopixelWrite(RGB_BUILTIN, 0, 0, 0); BaseHardware::IS_RGB_LED_ON=false; }
        static inline void TURN_RGBLED_ON(int color=1) { 
            switch (color) {
                case 0:
                    /* turn on white */
                    neopixelWrite(RGB_BUILTIN, BaseHardware::RGBLED_BRIGHTNESS, BaseHardware::RGBLED_BRIGHTNESS, BaseHardware::RGBLED_BRIGHTNESS);
                    break;
                case 1:
                    /* turn on red */
                    neopixelWrite(RGB_BUILTIN, BaseHardware::RGBLED_BRIGHTNESS, 0, 0);
                    break;
                case 2:
                    /* turn on green */
                    neopixelWrite(RGB_BUILTIN, 0, BaseHardware::RGBLED_BRIGHTNESS, 0);
                    break;
                case 3:
                    /* turn on blue */
                    neopixelWrite(RGB_BUILTIN, 0, 0, BaseHardware::RGBLED_BRIGHTNESS);
                    break;
                default:
                    return;
            }
            BaseHardware::IS_RGB_LED_ON=true;             
        }
        static inline void CHANGE_RGB_LED(int color) {
            if (BaseHardware::is_rgb_led_on()) BaseHardware::TURN_RGBLED_OFF();
            else BaseHardware::TURN_RGBLED_ON(color);
        }
        static inline void BLINK_RGB_LED(int color=1, int numBlinks=10, int delay_ms=300) {
            for (int i=0; i<numBlinks; i++) {
                BaseHardware::CHANGE_RGB_LED(color);
                delay(delay_ms);
            }
        }
        static inline void BLINK_WHINE_LED(int number=3, int delay_ms=300) { BaseHardware::BLINK_RGB_LED(0,number,delay_ms);}
        static inline void BLINK_RED_LED(int number=3, int delay_ms=300) { BaseHardware::BLINK_RGB_LED(1,number,delay_ms);}
        static inline void BLINK_GREEN_LED(int number=3, int delay_ms=300) { BaseHardware::BLINK_RGB_LED(2,number,delay_ms);}
        static inline void BLINK_BLUE_LED(int number=3, int delay_ms=300) { BaseHardware::BLINK_RGB_LED(3,number,delay_ms);}

        static inline void CHANGE_WHITE_LED() { BaseHardware::CHANGE_RGB_LED(0);}
        static inline void CHANGE_RED_LED() { BaseHardware::CHANGE_RGB_LED(1);}
        static inline void CHANGE_GREEN_LED() { BaseHardware::CHANGE_RGB_LED(2);}
        static inline void CHANGE_BLUE_LED() { BaseHardware::CHANGE_RGB_LED(3);}
};

#endif
