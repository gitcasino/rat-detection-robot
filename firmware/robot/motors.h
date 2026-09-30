#pragma once

/*
 * L298N drive stage.
 *
 * Speed is applied as PWM on the two enable inputs and direction on the four
 * logic inputs. Every function is a no-op until the pins are configured, so a
 * build with an incomplete pin map cannot move the chassis.
 */

#include <stdint.h>

#include "robot_logic.h"

namespace motors {

bool begin();
bool ready();

// Applies the requested manoeuvre. Stops are applied without PWM so the driver
// enable pins are pulled low rather than left floating at a duty cycle.
void apply(robotlogic::DriveCommand command, uint8_t speed_percent);
void stop();

uint8_t left_speed();
uint8_t right_speed();

}  // namespace motors
