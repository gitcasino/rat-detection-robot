#pragma once

/*
 * Telemetry and event transport.
 *
 * The control loop never waits on the network. Events are appended to a bounded
 * RAM queue and flushed opportunistically; a telemetry frame is sent on its own
 * cadence and doubles as the heartbeat. If the backend is unreachable the queue
 * holds what it can and the robot keeps running.
 */

#include <stdint.h>

#include <Arduino.h>

#include "robot_logic.h"

namespace telemetry {

enum class EventType : uint8_t {
  DeviceOnline,
  VibrationDetected,
  VibrationCleared,
  IrDetected,
  IrCleared,
  DistanceUpdated,
  TargetActivityDetected,
  TargetActivityCleared,
  RobotMoving,
  RobotStopped,
  EmitterActivated,
  EmitterDeactivated,
  ObstacleDetected,
  ObstacleCleared,
  Error,
  Heartbeat,
};

const char *event_type_name(EventType type);

// Everything the transport needs, decoupled from the modules that own the data.
struct Snapshot {
  robotlogic::RobotState robot_state = robotlogic::RobotState::Monitoring;
  const char *confirmation_mode_name = "disabled";
  const char *firmware_version = FIRMWARE_VERSION;

  bool vibration = false;
  bool vibration_configured = false;
  bool ir = false;
  bool ir_configured = false;
  bool distance_valid = false;
  float distance_cm = 0.0f;

  bool emitter_active = false;
  bool emitter_ready = false;
  bool drive_ready = false;

  bool wifi_connected = false;
  int32_t rssi = 0;
  String ip;
  String ssid;

  uint32_t uptime_ms = 0;
  bool clock_valid = false;
  String timestamp;
};

void begin();

// Queues one event. The queue is bounded and drops the oldest entry when full,
// counting the loss so it can be reported rather than hidden.
void record(EventType type, const Snapshot &snapshot, const char *message = nullptr);

// Performs at most one network operation per call.
void flush(uint32_t now_ms, const Snapshot &snapshot);

uint16_t pending();
uint32_t dropped();
bool last_send_succeeded();
bool configured();

}  // namespace telemetry
