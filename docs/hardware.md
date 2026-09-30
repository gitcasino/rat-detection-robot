# Hardware notes

Everything in this document is a wiring and verification aid. Nothing here was
confirmed with a meter: the photographs of the prototype were ambiguous about
which module sits behind which wire. Treat the pin assignments as unverified
until you check them against your own board.

## Known and unknown assignments

| Signal | Firmware macro | Value | Status |
| --- | --- | --- | --- |
| Ultrasonic trigger | `PIN_ULTRASONIC_TRIG` | `GPIO5` | Prototype value, unverified |
| Ultrasonic echo | `PIN_ULTRASONIC_ECHO` | `GPIO18` | Prototype value, unverified |
| Vibration / contact | `PIN_VIBRATION` | `-1` | Unknown, disabled |
| Infrared | `PIN_IR` | `-1` | Unknown, disabled |
| Motor A enable | `PIN_MOTOR_EN_A` | `-1` | Unknown, disabled |
| Motor B enable | `PIN_MOTOR_EN_B` | `-1` | Unknown, disabled |
| Motor IN1..IN4 | `PIN_MOTOR_IN_1..4` | `-1` | Unknown, disabled |
| Emitter driver | `PIN_EMITTER_DRIVER` | `-1` | Unknown, disabled |

`-1` is `PIN_UNCONFIGURED`. A subsystem with an unconfigured pin is disabled: the
firmware refuses to drive it, reports `ready() == false`, and raises an `ERROR`
event explaining what is missing. That is deliberate. Guessing a GPIO and
actuating an ultrasonic emitter or a motor bridge is how hardware gets damaged.

To enable a feature, set its pin in `firmware/robot/config.local.h` (or
`pins.h`) and confirm the direction with a meter first.

## HC-SR04 ultrasonic sensor

- 5 V powered, 3.3 V logic.
- **The echo pin must not be connected directly to a 3.3 V GPIO.** Use a
  1 kΩ / 2 kΩ divider (5 V -> 3.3 V) or a logic level shifter.
- The firmware times out at `CFG_ECHO_TIMEOUT_US` (25 ms) and reports an invalid
  reading rather than a fabricated distance when nothing answers.
- Mount it facing forward, below the bumper line, with the cone clear of wheels.
- Expect 2 to 5 cm of error on soft targets. Calibrate `CFG_DETECT_DISTANCE_CM`
  against a tape measure, not against a datasheet.

## Motor drive (L298N assumed)

The prototype uses an L298N-style dual H-bridge, but the enable/jumper wiring
could not be read from the photographs.

- Never drive a motor from a GPIO. The L298N takes the logic inputs from the
  ESP32 and the motor current from its own supply.
- Remove the onboard 5 V regulator jumper if the motor supply is above 12 V, and
  feed the ESP32 from a separate regulator.
- Common ground between the ESP32 and the motor driver is mandatory.
- The firmware uses `ledc` PWM on the enable pins; confirm the PWM frequency is
  acceptable for your driver (default 1 kHz).
- Add a physical kill: a switch in series with the motor supply. Software safety
  is not a substitute for being able to cut power with your hand.

## Emitter output

- Drive the emitter through a transistor or MOSFET stage with a gate/base
  resistor and a flyback diode for an inductive load. The ESP32 pin is a logic
  signal only.
- Respect the 3.3 V GPIO current limit: keep the driver input current well under
  12 mA, and switch the load current, not the ESP32.
- If the emitter is a piezo horn, remember it is capacitive; give the driver
  enough base/gate charge and consider a series resistor.
- The firmware reports the **command state**. There is no feedback input, so the
  console cannot claim that sound was produced. If you add an amplifier fault
  line or a piezo sense input, wire it to a spare GPIO and extend the telemetry
  contract rather than inferring success.

## Power budget

| Rail | Source | Notes |
| --- | --- | --- |
| ESP32 | 5 V USB or 3.3 V regulator | Peak current spikes during Wi-Fi TX |
| HC-SR04 | 5 V | 15 mA typical, spikes on transmit |
| L298N logic | 5 V from driver or ESP32 regulator | Depends on jumper position |
| Motors | 6 to 12 V, separate | Current peaks far above logic rails |
| Emitter stage | Its own supply | Never from a GPIO rail |

Add bulk capacitance (100 to 470 µF) at the motors and the emitter driver. Brownouts
during Wi-Fi transmission are the most common cause of "the robot reboots when the
emitter fires".

## Sensors are not detectors

- An ultrasonic reading says something is 20 cm away. It does not say what.
- The vibration/contact channel says something is moving against the chassis.
- The infrared channel says something broke a beam.
- Together they justify `TARGET_ACTIVITY`. On their own they justify at most a
  proximity event. Keep the event names honest: the console maps
  `TARGET_ACTIVITY_DETECTED` to "Activity detected", never to "rat detected".

For genuine species identification you would add a camera module or a PIR
sensor, and change the schema explicitly.

## Verification checklist before first power-on

1. Continuity-check the motor driver inputs to the ESP32 pins you intend to use.
2. Confirm the echo divider reduces 5 V to about 3.3 V with the sensor plugged in.
3. Measure the emitter driver gate/base voltage with the firmware idle: it must be
   0 V, because the firmware starts with the emitter command off.
4. Verify the driver common ground with a meter between the ESP32 and the driver.
5. Set `CFG_TARGET_CONFIRMATION` to `TARGET_CONFIRM_DISABLED` for the first
   bench run, then re-enable fusion once the drive and sensors behave.
6. Lift the wheels off the ground for the first powered run, with your hand on the
   power switch.
7. Watch the serial log at 115200 baud: unconfigured subsystems are reported as
   errors on purpose.
