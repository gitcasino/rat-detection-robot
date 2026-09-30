/*
 * Smart Rat Detection and Repellent Robot - firmware entry point.
 *
 * Loop shape:
 *
 *   1. acquire sensors          (non-blocking)
 *   2. run the control machine  (pure logic, see robot_logic.cpp)
 *   3. apply the outputs        (motors + emitter, each through one owner module)
 *   4. record events            (bounded RAM queue)
 *   5. transmit at most one network operation per tick
 *
 * The physical loop never blocks on the network. If the backend disappears the
 * robot keeps detecting, driving and repelling; telemetry resumes on its own.
 */

#include <Arduino.h>

#include "config.h"
#include "emitter.h"
#include "motors.h"
#include "robot_network.h"
#include "robot_logic.h"
#include "sensors.h"
#include "telemetry.h"

namespace {

// Startup guard. The emitter and the drive are forced to their inactive levels
// before the control machine is allowed to influence anything.
constexpr uint32_t CONTROL_ARM_DELAY_MS = 500;

robotlogic::Controller g_controller;
bool g_announced_online = false;
uint32_t g_boot_ms = 0;
uint32_t g_arm_ms = 0;
bool g_config_reported = false;

telemetry::Snapshot build_snapshot(uint32_t now_ms) {
  const sensors::State &sensor_state = sensors::state();

  telemetry::Snapshot snapshot;
  snapshot.robot_state = g_controller.state();
  snapshot.confirmation_mode_name = robotlogic::Controller::confirmation_name(
      g_controller.activity_confirmed()
          ? CFG_TARGET_CONFIRMATION
          : TARGET_CONFIRM_DISABLED);
  snapshot.vibration = sensor_state.vibration_active;
  snapshot.vibration_configured = sensor_state.vibration_configured;
  snapshot.ir = sensor_state.ir_active;
  snapshot.ir_configured = sensor_state.ir_configured;
  snapshot.distance_valid = sensor_state.distance_valid;
  snapshot.distance_cm = sensor_state.distance_cm;

  snapshot.emitter_active = emitter::active();
  snapshot.emitter_ready = emitter::ready();
  snapshot.drive_ready = motors::ready();

  snapshot.wifi_connected = robot_network::connected();
  snapshot.rssi = robot_network::status().rssi;
  snapshot.ip = robot_network::status().ip;
  snapshot.ssid = robot_network::status().ssid;

  snapshot.uptime_ms = now_ms - g_boot_ms;
  snapshot.clock_valid = robot_network::clock_valid();
  snapshot.timestamp = robot_network::iso8601();
  return snapshot;
}

void report_configuration(const telemetry::Snapshot &snapshot) {
  if (g_config_reported) {
    return;
  }
  g_config_reported = true;

  if (!robot_network::credentials_configured()) {
    Serial.println(F("[boot] WIFI_SSID is empty: telemetry disabled, robot runs locally"));
    telemetry::record(telemetry::EventType::Error, snapshot,
                      "WIFI_SSID not configured; telemetry disabled");
  }
  if (!emitter::ready()) {
    Serial.println(F("[boot] PIN_EMITTER_DRIVER is unconfigured: emitter disabled"));
    telemetry::record(telemetry::EventType::Error, snapshot,
                      "PIN_EMITTER_DRIVER unconfigured; emitter disabled");
  }
  if (!motors::ready()) {
    Serial.println(F("[boot] motor pins unconfigured: drive disabled"));
    telemetry::record(telemetry::EventType::Error, snapshot,
                      "L298N pins unconfigured; drive disabled");
  }
  if (!sensors::state().vibration_configured) {
    Serial.println(F("[boot] PIN_VIBRATION unconfigured: fusion needs another channel"));
  }
  if (!sensors::state().ir_configured) {
    Serial.println(F("[boot] PIN_IR unconfigured: fusion needs another channel"));
  }
}

void emit_transition(const robotlogic::Transition &transition, const telemetry::Snapshot &snapshot) {
  switch (transition.kind) {
    case robotlogic::TransitionKind::TargetActivityDetected:
      telemetry::record(telemetry::EventType::TargetActivityDetected, snapshot,
                        "Sensor fusion confirmed activity");
      break;
    case robotlogic::TransitionKind::TargetActivityCleared:
      telemetry::record(telemetry::EventType::TargetActivityCleared, snapshot,
                        "Activity no longer confirmed");
      break;
    case robotlogic::TransitionKind::ObstacleDetected:
      telemetry::record(telemetry::EventType::ObstacleDetected, snapshot,
                        "Obstacle inside clearance threshold");
      break;
    case robotlogic::TransitionKind::ObstacleCleared:
      telemetry::record(telemetry::EventType::ObstacleCleared, snapshot, "Path ahead clear");
      break;
    case robotlogic::TransitionKind::Fault:
      telemetry::record(telemetry::EventType::Error, snapshot,
                        "Control fault: hardware incomplete or distance sensor lost");
      break;
    case robotlogic::TransitionKind::None:
    case robotlogic::TransitionKind::EmitterActivated:
    case robotlogic::TransitionKind::EmitterDeactivated:
      // Emitter transitions are derived from emitter::set_active(), which is the
      // only place the command actually changes. Reporting them anywhere else
      // would allow the log to disagree with the hardware.
      break;
  }
}

void track_sensor_edges(const sensors::State &current, bool &previous_vibration, bool &previous_ir,
                        const telemetry::Snapshot &snapshot) {
  if (current.vibration_configured && current.vibration_active != previous_vibration) {
    telemetry::record(current.vibration_active ? telemetry::EventType::VibrationDetected
                                               : telemetry::EventType::VibrationCleared,
                      snapshot, current.vibration_active ? "Vibration sensor triggered"
                                                        : "Vibration sensor idle");
    previous_vibration = current.vibration_active;
  }
  if (current.ir_configured && current.ir_active != previous_ir) {
    telemetry::record(
        current.ir_active ? telemetry::EventType::IrDetected : telemetry::EventType::IrCleared,
        snapshot, current.ir_active ? "IR sensor triggered" : "IR sensor idle");
    previous_ir = current.ir_active;
  }
}

}  // namespace

void setup() {
  Serial.begin(CFG_SERIAL_BAUD);
  const uint32_t now = millis();
  g_boot_ms = now;

  Serial.println();
  Serial.println(F("Smart Rat Detection and Repellent Robot"));
  Serial.print(F("firmware "));
  Serial.print(FIRMWARE_VERSION);
  Serial.print(F(" device "));
  Serial.println(DEVICE_ID);

  emitter::begin();
  motors::begin();
  sensors::begin();
  telemetry::begin();
  robot_network::begin();

  // Nothing may drive before the arm delay expires.
  motors::stop();
  emitter::force_off();
  g_arm_ms = now + CONTROL_ARM_DELAY_MS;
}

void loop() {
  const uint32_t now = millis();

  robot_network::tick(now);
  sensors::poll(now);

  const sensors::State &sensor_state = sensors::state();

  robotlogic::Inputs inputs;
  inputs.vibration_active = sensor_state.vibration_active;
  inputs.ir_active = sensor_state.ir_active;
  inputs.vibration_configured = sensor_state.vibration_configured;
  inputs.ir_configured = sensor_state.ir_configured;
  inputs.distance_valid = sensor_state.distance_valid;
  inputs.distance_cm = sensor_state.distance_cm;
  inputs.drive_ready = motors::ready();
  inputs.emitter_ready = emitter::ready();

  const robotlogic::StepResult step = g_controller.update(inputs, now);
  telemetry::Snapshot snapshot = build_snapshot(now);
  report_configuration(snapshot);

  emit_transition(step.transition, snapshot);
  if (step.has_secondary) {
    emit_transition(step.secondary, snapshot);
  }

  // Outputs only after the arm delay, so a noisy boot cannot move the chassis.
  const bool armed = now >= g_arm_ms;
  if (armed) {
    motors::apply(step.outputs.drive, step.outputs.speed_percent);
  } else {
    motors::stop();
  }

  // One owner for the emitter command; a state change here is the event.
  if (emitter::set_active(step.outputs.emitter_request)) {
    snapshot.emitter_active = emitter::active();
    if (emitter::active()) {
      telemetry::record(telemetry::EventType::EmitterActivated, snapshot,
                        "Emitter command set ACTIVE");
    } else {
      telemetry::record(telemetry::EventType::EmitterDeactivated, snapshot,
                        "Emitter command set INACTIVE");
    }
  }
  emitter::tick(now);

  static bool previous_vibration = false;
  static bool previous_ir = false;
  track_sensor_edges(sensor_state, previous_vibration, previous_ir, snapshot);

  if (robot_network::connected() && !g_announced_online) {
    g_announced_online = true;
    telemetry::record(telemetry::EventType::DeviceOnline, snapshot, "Robot associated with Wi-Fi");
  } else if (!robot_network::connected()) {
    g_announced_online = false;
  }

#if CFG_EMIT_HEARTBEAT_EVENTS
  static uint32_t last_heartbeat_ms = 0;
  if (robot_network::connected() && (now - last_heartbeat_ms) >= CFG_HEARTBEAT_INTERVAL_MS) {
    last_heartbeat_ms = now;
    telemetry::record(telemetry::EventType::Heartbeat, snapshot, "Device heartbeat");
  }
#endif

  telemetry::flush(now, snapshot);
  delay(2);
}
