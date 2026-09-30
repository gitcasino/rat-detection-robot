/* HTTPClient API stubs for offline syntax checking. See Arduino.h in this folder. */
#pragma once

#include <Arduino.h>

#include "WiFiClient.h"

class HTTPClient {
 public:
  void setConnectTimeout(uint32_t timeout_ms);
  void setTimeout(uint32_t timeout_ms);
  bool begin(const String &url);
  void addHeader(const String &name, const String &value);
  int POST(const String &payload);
  int GET();
  void end();
};
