#pragma once

/*
 * Wi-Fi association and time synchronisation.
 *
 * Association is non-blocking: tick() drives the state machine and the caller
 * keeps running its control loop regardless of link state. A telemetry failure
 * never gates the physical behaviour of the robot.
 */

#include <stdint.h>

#include <Arduino.h>

namespace network {

struct Status {
  bool connected = false;
  int32_t rssi = 0;
  String ip;
  String ssid;
  bool clock_valid = false;
};

bool begin();
void tick(uint32_t now_ms);

bool connected();
bool clock_valid();
const Status &status();

uint32_t uptime_ms();
uint32_t epoch_ms();
String iso8601();
bool credentials_configured();

}  // namespace network
