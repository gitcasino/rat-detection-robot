/* WiFi API stubs for offline syntax checking. See Arduino.h in this folder. */
#pragma once

#include <Arduino.h>

enum wl_status_t {
  WL_IDLE_STATUS = 0,
  WL_CONNECTED = 3,
  WL_CONNECT_FAILED = 4,
  WL_DISCONNECTED = 6,
};

enum WiFiMode { WIFI_OFF = 0, WIFI_STA = 1, WIFI_AP = 2 };

class WiFiClass {
 public:
  void begin(const char *ssid, const char *password);
  void disconnect(bool wifi_off = false);
  bool mode(WiFiMode value);
  bool setSleep(bool enable);
  wl_status_t status();
  String SSID();
  int32_t RSSI();
  IPAddress localIP();
};

extern WiFiClass WiFi;
