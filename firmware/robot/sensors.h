#pragma once

/*
 * Sensor acquisition.
 *
 * All sampling is non-blocking: the ultrasonic burst is started from poll() and
 * completed on a later call, so the control loop is never blocked waiting for an
 * echo pulse.
 */

#include <stdint.h>

namespace sensors {

struct State {
  bool distance_valid = false;
  float distance_cm = 0.0f;
  bool echo_timed_out = false;
  uint32_t distance_updated_ms = 0;
  uint32_t echo_failures = 0;

  bool vibration_configured = false;
  bool vibration_active = false;
  bool ir_configured = false;
  bool ir_active = false;
};

// Configures the pins this build actually has. Safe to call with unconfigured
// pins: the affected channel reports itself as not configured.
bool begin();

// Starts or completes a measurement and refreshes the debounced digital inputs.
void poll(uint32_t now_ms);

const State &state();

}  // namespace sensors
