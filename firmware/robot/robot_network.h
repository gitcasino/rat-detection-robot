#pragma once

/*
 * Wi-Fi association and time synchronisation.
 *
 * Association is non-blocking: tick() drives the state machine and the caller
 * keeps running its control loop regardless of link state. A telemetry failure
 * never gates the physical behaviour of the robot.
 *
 * The file and namespace are prefixed with `robot_` deliberately. The ESP32
 * Arduino core ships its own `Network.h`, and a case-insensitive filesystem
 * (Windows, and macOS by default) would collapse this module's unprefixed
 * header onto it, so an include of the bare name could resolve to core code
 * depending on search order. The prefix removes that ambiguity permanently.
 */

#include <stdint.h>

#include <Arduino.h>

namespace robot_network {

// Device-side Wi-Fi link state. This is deliberately not named LinkStatus:
// that name already belongs to the backend/frontend transport-health contract
// (websocket, websocket_clients, backend online/offline), which is a different
// concept. It matches the emitter::Status convention used by the other owner
// modules in this firmware.
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

}  // namespace robot_network
