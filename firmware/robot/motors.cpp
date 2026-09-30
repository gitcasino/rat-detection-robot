#include "motors.h"

#include <Arduino.h>

#include "config.h"
#include "pins.h"

namespace motors {
namespace {

constexpr uint32_t PWM_FREQUENCY_HZ = 1000;
constexpr uint8_t PWM_RESOLUTION_BITS = 8;
constexpr uint8_t PWM_MAX_VALUE = (1 << PWM_RESOLUTION_BITS) - 1;

bool g_ready = false;
uint8_t g_left = 0;
uint8_t g_right = 0;

bool pins_configured() {
  return PIN_MOTOR_EN_A != PIN_UNCONFIGURED && PIN_MOTOR_EN_B != PIN_UNCONFIGURED &&
         PIN_MOTOR_IN_1 != PIN_UNCONFIGURED && PIN_MOTOR_IN_2 != PIN_UNCONFIGURED &&
         PIN_MOTOR_IN_3 != PIN_UNCONFIGURED && PIN_MOTOR_IN_4 != PIN_UNCONFIGURED;
}

uint8_t scale(uint8_t percent) {
  if (percent > 100) {
    percent = 100;
  }
  return static_cast<uint8_t>((static_cast<uint16_t>(percent) * PWM_MAX_VALUE) / 100);
}

void set_direction(int in1, int in2, bool forward) {
  const int high = forward ? HIGH : LOW;
  const int low = forward ? LOW : HIGH;
  digitalWrite(in1, high);
  digitalWrite(in2, low);
}

void write_speed(uint8_t left, uint8_t right) {
  g_left = left;
  g_right = right;
  ledcWrite(PIN_MOTOR_EN_A, left);
  ledcWrite(PIN_MOTOR_EN_B, right);
}

}  // namespace

bool begin() {
  if (!pins_configured()) {
    g_ready = false;
    return false;
  }
  pinMode(PIN_MOTOR_EN_A, OUTPUT);
  pinMode(PIN_MOTOR_EN_B, OUTPUT);
  for (const int pin : {PIN_MOTOR_IN_1, PIN_MOTOR_IN_2, PIN_MOTOR_IN_3, PIN_MOTOR_IN_4}) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, LOW);
  }
#if defined(ESP32)
  ledcAttach(PIN_MOTOR_EN_A, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS);
  ledcAttach(PIN_MOTOR_EN_B, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS);
  ledcWrite(PIN_MOTOR_EN_A, 0);
  ledcWrite(PIN_MOTOR_EN_B, 0);
#endif
  g_ready = true;
  return true;
}

void stop() {
  if (!g_ready) {
    return;
  }
  write_speed(0, 0);
  set_direction(PIN_MOTOR_IN_1, PIN_MOTOR_IN_2, false);
  set_direction(PIN_MOTOR_IN_3, PIN_MOTOR_IN_4, false);
  digitalWrite(PIN_MOTOR_IN_1, LOW);
  digitalWrite(PIN_MOTOR_IN_2, LOW);
  digitalWrite(PIN_MOTOR_IN_3, LOW);
  digitalWrite(PIN_MOTOR_IN_4, LOW);
}

void apply(robotlogic::DriveCommand command, uint8_t speed_percent) {
  if (!g_ready) {
    return;
  }
  if (command == robotlogic::DriveCommand::Stop || speed_percent == 0) {
    stop();
    return;
  }

  const uint8_t duty = scale(speed_percent);
  switch (command) {
    case robotlogic::DriveCommand::Forward:
      set_direction(PIN_MOTOR_IN_1, PIN_MOTOR_IN_2, !MOTOR_A_INVERTED);
      set_direction(PIN_MOTOR_IN_3, PIN_MOTOR_IN_4, !MOTOR_B_INVERTED);
      write_speed(duty, duty);
      break;
    case robotlogic::DriveCommand::Reverse:
      set_direction(PIN_MOTOR_IN_1, PIN_MOTOR_IN_2, MOTOR_A_INVERTED);
      set_direction(PIN_MOTOR_IN_3, PIN_MOTOR_IN_4, MOTOR_B_INVERTED);
      write_speed(duty, duty);
      break;
    case robotlogic::DriveCommand::TurnRight:
      set_direction(PIN_MOTOR_IN_1, PIN_MOTOR_IN_2, !MOTOR_A_INVERTED);
      set_direction(PIN_MOTOR_IN_3, PIN_MOTOR_IN_4, MOTOR_B_INVERTED);
      write_speed(duty, duty);
      break;
    case robotlogic::DriveCommand::TurnLeft:
      set_direction(PIN_MOTOR_IN_1, PIN_MOTOR_IN_2, MOTOR_A_INVERTED);
      set_direction(PIN_MOTOR_IN_3, PIN_MOTOR_IN_4, !MOTOR_B_INVERTED);
      write_speed(duty, duty);
      break;
    case robotlogic::DriveCommand::Stop:
      break;
  }
}

bool ready() { return g_ready; }
uint8_t left_speed() { return g_left; }
uint8_t right_speed() { return g_right; }

}  // namespace motors
