# Usage
## Common dependencies
There are some dependencies to be always added to the project (required for correct backend communications). Including:
- ESPAsyncWebServer-esphome (used to collect backend data). This will automatically add some other dependencies — AsyncTCP-esphome and ESPAsyncTCP-esphome (for ESP8266 only)
- PubSubClient (MQTT client is used for all MQTT communications in conjunction with standard arduino-esp32 WiFiClientSecure for TCP connections with MTLS)
- ArduinoJSON (used for serializing and deserializing MQTT messages)
## Thing specific dependencies
Depending from sensors and other peripherals connected to your thing you may need to install extra libraries. One of the most common library for working with sensors is [Adafruit Unified Sensor Driver](https://github.com/adafruit/Adafruit_Sensor) accompanied with particular library for your sensor (for example [DHT sensor library](https://github.com/adafruit/DHT-sensor-library))


## Make changes in config files


## Configure the VSCode
- install PlatformIO extension

## PlatformIO configuration
- update your default serial speed (for ESP32 it's 115200) by adding line to the `platformio.ini`
```
monitor_speed = 115200
```
- add required libraries with PlatformIO Libraries Manager
    - ESPAsyncWebServer-esphome
    - ArduinoJson
    - PubSubClient
- prepare and add certificates bundle (see below)

### Prepare certificates bundle
- create & activate python3 venv
- install `cryptography` module in venv
- collect `cacrt_all.pem` from https://github.com/espressif/esp-idf/blob/master/components/mbedtls/esp_crt_bundle/cacrt_all.pem
- run `python gen_crt_bundle.py -i cacrt_all.pem` in the activated venv
- rename `x509_crt_bundle` to `x509_crt_bundle.bin`
- move `x509_crt_bundle.bin` to `data/cert/x509_crt_bundle.bin`
- add a line `board_build.embed_files = data/cert/x509_crt_bundle.bin` to `platformio.ini`
- add code in your project:
    ```python
    extern const uint8_t rootca_crt_bundle_start[] asm("_binary_data_cert_x509_crt_bundle_bin_start");

    ...

        client.setCACertBundle(rootca_crt_bundle_start);

    ```

### Example `platformio.ini` after configuration:
```
[env:sparkfun_esp32s2_thing_plus_c]
platform = espressif32
board = sparkfun_esp32s2_thing_plus_c
framework = arduino
monitor_speed = 115200
board_build.embed_files = data/cert/x509_crt_bundle.bin
lib_deps = ottowinter/ESPAsyncWebServer-esphome@^3.0.0
```
