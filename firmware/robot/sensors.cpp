#include "sensors.h"

#include <Arduino.h>

#include "config.h"

namespace sensors {
namespace {

enum class EchoPhase : uint8_t { Idle, Waiting };

constexpr uint32_t TRIGGER_PULSE_US = 10;
constexpr uint32_t ECHO_MIN_US = 400;      // below this the pulse is noise
constexpr float US_TO_CM = 0.01715f;       // 343 m/s, halved for the round trip

EchoPhase g_phase = EchoPhase::Idle;
uint32_t g_trigger_us = 0;
uint32_t g_last_trigger_ms = 0;

State g_state;

// Digital inputs are debounced: cheap sensor modules chatter for tens of
// milliseconds around a transition.
struct DebouncedInput {
  int pin = PIN_UNCONFIGURED;
  bool configured = false;
  bool active_low = false;
  bool raw = false;
  bool stable = false;
  bool candidate = false;
  uint32_t candidate_since_ms = 0;
};

DebouncedInput g_vibration;
DebouncedInput g_ir;

bool read_active(int pin, const DebouncedInput &input) {
  const int level = digitalRead(pin);
  return input.active_low ? (level == LOW) : (level == HIGH);
}

void configure_input(DebouncedInput &input, int pin, bool active_low) {
  if (pin == PIN_UNCONFIGURED) {
    input.configured = false;
    return;
  }
  pinMode(pin, INPUT_PULLUP);
  input.pin = pin;
  input.configured = true;
  input.active_low = active_low;
  input.raw = read_active(pin, input);
  input.stable = input.raw;
  input.candidate = input.raw;
}

void update_input(DebouncedInput &input, uint32_t now_ms) {
  if (!input.configured) {
    return;
  }
  const bool level = read_active(input.pin, input);
  if (level != input.candidate) {
    input.candidate = level;
    input.candidate_since_ms = now_ms;
    return;
  }
  if (input.stable == input.candidate) {
    return;
  }
  if ((now_ms - input.candidate_since_ms) >= CFG_SENSOR_DEBOUNCE_MS) {
    input.stable = input.candidate;
  }
}

void start_echo() {
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);
  // The HC-SR04 requires a 10 us high level on TRIG. This is the one place where
  // a microsecond-scale busy wait is acceptable: a spin loop would block for
  // longer and gain nothing.
  delayMicroseconds(TRIGGER_PULSE_US);
  digitalWrite(PIN_ULTRASONIC_TRIG, HIGH);
  g_trigger_us = micros();
  g_phase = EchoPhase::Waiting;
}

void poll_echo(uint32_t now_ms) {
  if (g_phase == EchoPhase::Idle) {
    if ((now_ms - g_last_trigger_ms) >= CFG_DISTANCE_SAMPLE_INTERVAL_MS) {
      g_last_trigger_ms = now_ms;
      start_echo();
    }
    return;
  }

  const uint32_t elapsed_us = micros() - g_trigger_us;
  const int level = digitalRead(PIN_ULTRASONIC_ECHO);

  if (level == LOW) {
    // Still inside the pulse: a reading below the physical minimum is noise.
    if (elapsed_us >= ECHO_MIN_US) {
      g_state.distance_cm = elapsed_us * US_TO_CM;
      g_state.distance_valid = g_state.distance_cm > 0.0f;
      g_state.echo_timed_out = false;
      g_state.distance_updated_ms = now_ms;
      g_phase = EchoPhase::Idle;
    }
    return;
  }

  if (elapsed_us < CFG_ECHO_TIMEOUT_US) {
    g_state.distance_cm = elapsed_us * US_TO_CM;
    g_state.distance_valid = g_state.distance_cm > 0.0f;
    g_state.echo_timed_out = false;
    g_state.distance_updated_ms = now_ms;
    g_phase = EchoPhase::Idle;
    return;
  }

  // No rising edge within the timeout: the sensor is unconnected, obstructed or
  // out of range. Report it instead of reusing the previous value.
  g_state.distance_valid = false;
  g_state.distance_cm = 0.0f;
  g_state.echo_timed_out = true;
  g_state.echo_failures++;
  g_phase = EchoPhase::Idle;
}

}  // namespace

bool begin() {
  pinMode(PIN_ULTRASONIC_TRIG, OUTPUT);
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);
  pinMode(PIN_ULTRASONIC_ECHO, INPUT);

  configure_input(g_vibration, PIN_VIBRATION, VIBRATION_ACTIVE_LOW);
  configure_input(g_ir, PIN_IR, IR_ACTIVE_HIGH);

  g_state.vibration_configured = g_vibration.configured;
  g_state.ir_configured = g_ir.configured;
  g_phase = EchoPhase::Idle;
  g_last_trigger_ms = 0;
  return true;
}

void poll(uint32_t now_ms) {
  poll_echo(now_ms);
  update_input(g_vibration, now_ms);
  update_input(g_ir, now_ms);

  g_state.vibration_active = g_vibration.configured && g_vibration.stable;
  g_state.ir_active = g_ir.configured && g_ir.stable;
}

const State &state() { return g_state; }

}  // namespace sensors
