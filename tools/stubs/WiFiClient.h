/* WiFiClient stub for offline syntax checking. See Arduino.h in this folder. */
#pragma once

#include <Arduino.h>

class WiFiClient {
 public:
  bool connect(const char *host, uint16_t port);
  bool connected();
  void stop();
  size_t write(const uint8_t *data, size_t size);
};
