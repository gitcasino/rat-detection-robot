/*
 * Arduino API stubs for offline syntax checking.
 *
 * These are NOT a simulator and NOT used by the firmware build. They exist so the
 * Arduino-facing translation units can be type-checked on a machine without the
 * Arduino toolchain:
 *
 *     bash tools/check_firmware.sh
 *
 * Signatures mirror the real ESP32 core closely enough to catch typos, wrong
 * argument counts and missing declarations. Behaviour is intentionally empty.
 */

#pragma once

#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <ctime>

#define F(x) (x)
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2

#ifndef LEDC_CHANNEL_0
#define LEDC_CHANNEL_0 0
#endif

typedef bool boolean;

class String {
 public:
  String() = default;
  String(const char *value) : value_(value == nullptr ? "" : value) {}
  String(const std::string &value) : value_(value) {}
  String(int value) : value_(std::to_string(value)) {}
  String(unsigned int value) : value_(std::to_string(value)) {}
  String(long value) : value_(std::to_string(value)) {}
  String(unsigned long value) : value_(std::to_string(value)) {}

  String &operator=(const char *value) {
    value_ = value == nullptr ? "" : value;
    return *this;
  }
  String &operator+=(const String &other) {
    value_ += other.value_;
    return *this;
  }
  String &operator+=(const char *other) {
    value_ += other;
    return *this;
  }
  friend String operator+(const String &left, const String &right) {
    String combined(left.value_);
    combined += right;
    return combined;
  }
  friend String operator+(const String &left, const char *right) {
    String combined(left.value_);
    combined += right;
    return combined;
  }
  const char *c_str() const { return value_.c_str(); }
  bool length() const { return value_.size() > 0; }
  operator bool() const { return !value_.empty(); }

 private:
  std::string value_;
};

class HardwareSerial {
 public:
  void begin(unsigned long) {}
  void println() {}
  void println(const char *) {}
  void println(const String &) {}
  void println(int) {}
  void print(const char *) {}
  void print(const String &) {}
  void print(unsigned long) {}
  void println(unsigned long) {}
  void print(int) {}
};

extern HardwareSerial Serial;

unsigned long millis();
unsigned long micros();
void delay(unsigned long);
void delayMicroseconds(unsigned int);
void pinMode(uint8_t pin, uint8_t mode);
int digitalRead(uint8_t pin);
void digitalWrite(uint8_t pin, uint8_t value);
void ledcAttach(uint8_t pin, uint32_t frequency, uint8_t resolution);
void ledcWrite(uint8_t pin, uint32_t duty);
void configTime(long gmt_offset_sec, int daylight_offset_sec, const char *server1);
bool getLocalTime(struct tm *info, uint32_t timeout_ms = 5000);
time_t time(time_t *timer);

class IPAddress {
 public:
  IPAddress() = default;
  IPAddress(uint32_t address) : address_(address) {}
  uint32_t toUint32() const { return address_; }
  String toString() const { return String("0.0.0.0"); }

 private:
  uint32_t address_ = 0;
};
