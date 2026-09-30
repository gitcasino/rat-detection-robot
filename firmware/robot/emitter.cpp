#include "emitter.h"

#include <Arduino.h>

#include "config.h"
#include "pins.h"

namespace emitter {
namespace {

// Independent upper bound on a single activation. The control logic ends bursts
// on its own; this exists so a logic fault can never leave the transducer driven
// continuously.
constexpr uint32_t MAX_CONTINUOUS_MS = CFG_EMITTER_BURST_MS + 2000UL;

Status g_status;
uint32_t g_active_since_ms = 0;

void write_pin(bool active) {
#if EMITTER_ACTIVE_HIGH
  digitalWrite(PIN_EMITTER_DRIVER, active ? HIGH : LOW);
#else
  digitalWrite(PIN_EMITTER_DRIVER, active ? LOW : HIGH);
#endif
}

}  // namespace

bool begin() {
  if (PIN_EMITTER_DRIVER == PIN_UNCONFIGURED) {
    g_status.ready = false;
    g_status.active = false;
    return false;
  }
  pinMode(PIN_EMITTER_DRIVER, OUTPUT);
  write_pin(false);
  g_status.ready = true;
  g_status.active = false;
  g_active_since_ms = 0;
  return true;
}

bool set_active(bool active) {
  if (!g_status.ready) {
    return false;
  }
  if (active == g_status.active) {
    return false;
  }

  const uint32_t now = millis();
  write_pin(active);
  g_status.active = active;
  if (active) {
    g_status.activations++;
    g_status.last_activated_ms = now;
    g_active_since_ms = now;
  } else {
    if (g_active_since_ms != 0) {
      g_status.active_ms_total += now - g_active_since_ms;
    }
    g_status.last_deactivated_ms = now;
    g_active_since_ms = 0;
  }
  return true;
}

void force_off() { set_active(false); }

void tick(uint32_t now_ms) {
  if (!g_status.ready || !g_status.active) {
    return;
  }
  if ((now_ms - g_active_since_ms) > MAX_CONTINUOUS_MS) {
    set_active(false);
  }
}

bool active() { return g_status.active; }
bool ready() { return g_status.ready; }
const Status &status() { return g_status; }

}  // namespace emitter
