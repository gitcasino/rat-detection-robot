#pragma once

/*
 * Emitter command state.
 *
 * This module is the single owner of the emitter output pin. Nothing else in the
 * firmware writes it, which is what makes the reported emitter state
 * trustworthy: the dashboard shows the commanded state that was actually applied
 * to the driver, not a copy of some other variable.
 *
 * The reported state is a COMMAND state. Unless a feedback circuit is wired to
 * an input pin and sampled here, nothing in this firmware can prove that the
 * transducer is producing acoustic output.
 */

#include <stdint.h>

namespace emitter {

struct Status {
  bool ready = false;          // an output pin is configured in pins.h
  bool active = false;         // commanded state applied to the driver
  uint32_t activations = 0;
  uint32_t last_activated_ms = 0;
  uint32_t last_deactivated_ms = 0;
  uint32_t active_ms_total = 0;
};

// Drives the output to its inactive level immediately. Called before the control
// loop is ready so the emitter can never be active during startup.
bool begin();

// The only function that writes the emitter pin. Returns true when the commanded
// state changed, which is the exact moment an EMITTER_ACTIVATED or
// EMITTER_DEACTIVATED event belongs in the log.
bool set_active(bool active);

bool active();
bool ready();
void force_off();
void tick(uint32_t now_ms);

const Status &status();

}  // namespace emitter
