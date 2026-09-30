#pragma once

/*
 * ---------------------------------------------------------------------------
 * GPIO MAP - the only place in the firmware where pin numbers appear.
 * ---------------------------------------------------------------------------
 *
 * PROVENANCE OF THE VALUES BELOW
 *
 *   VERIFIED BY EXISTING FIRMWARE
 *     HC-SR04 TRIG -> GPIO5
 *     HC-SR04 ECHO -> GPIO18
 *     These come from the working prototype sketch. They describe the software
 *     that existed, not a verified view of the assembled robot: the wiring has
 *     not been confirmed against the physical build in this repository.
 *
 *   NOT VERIFIED - REQUIRES PHYSICAL CONFIRMATION
 *     Every other pin below is a placeholder. A value of -1 means "not
 *     configured": the owning subsystem stays disabled, refuses to drive any
 *     output, and the firmware raises a single ERROR event at boot. This is
 *     deliberate. Guessing a GPIO and writing to it risks driving the wrong
 *     circuit or fighting the L298N enable lines.
 *
 *     Fill these in after tracing the actual wiring, then remove the -1.
 *
 * ELECTRICAL SAFETY (ESP32 GPIO is 3.3 V logic only)
 *
 *   * A standard HC-SR04 drives ECHO to 5 V. Divide or level-shift ECHO before
 *     it reaches GPIO18, otherwise the ESP32 input is over-stressed.
 *   * Motor and emitter loads must not be driven from a GPIO pin directly.
 *     Use the L298N input/logic pins and a transistor or MOSFET gate stage for
 *     the ultrasonic emitter, with a common ground reference.
 *   * The ESP32 3V3 rail cannot supply the L298N motor rail or the emitter.
 */

#define PIN_UNCONFIGURED (-1)

// --- Ultrasonic distance sensor (HC-SR04) ------------------------------------
#define PIN_ULTRASONIC_TRIG 5
#define PIN_ULTRASONIC_ECHO 18

// --- Vibration sensor (digital output module, e.g. SW-420 style) ------------
// REQUIRES CONFIRMATION: type of module and whether OUT goes high or low on
// detection. A bare spring switch needs a pull-up plus a Schmitt trigger.
#define PIN_VIBRATION (-1)
#define VIBRATION_ACTIVE_LOW true

// --- IR sensor (digital output module, e.g. HC-SR501 / TCRT style) ----------
// REQUIRES CONFIRMATION: module model and output polarity.
#define PIN_IR (-1)
#define IR_ACTIVE_HIGH true

// --- L298N motor driver -----------------------------------------------------
// REQUIRES CONFIRMATION: ENA/ENB are the two PWM speed inputs, IN1..IN4 set
// direction. Verify which physical header each wire lands on.
#define PIN_MOTOR_EN_A (-1)
#define PIN_MOTOR_EN_B (-1)
#define PIN_MOTOR_IN_1 (-1)
#define PIN_MOTOR_IN_2 (-1)
#define PIN_MOTOR_IN_3 (-1)
#define PIN_MOTOR_IN_4 (-1)

// Left motors on channel A, right motors on channel B. Inverting a side is the
// usual fix for a mirrored two-wheel chassis.
#define MOTOR_A_INVERTED false
#define MOTOR_B_INVERTED false

// --- Ultrasonic emitter driver ----------------------------------------------
// REQUIRES CONFIRMATION: this is the GATE input of the transistor/MOSFET that
// switches transducer power. It is not a power output. Confirm the gate
// polarity of the driver stage actually fitted.
#define PIN_EMITTER_DRIVER (-1)
#define EMITTER_ACTIVE_HIGH true
