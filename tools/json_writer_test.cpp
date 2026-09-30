/*
 * Native test harness for the telemetry JSON writer.
 *
 * The payload format is the contract between firmware and backend, so it is
 * worth checking on a workstation rather than on a bench with a serial monitor.
 *
 * Build and run (from the repository root):
 *     g++ -std=c++17 -Wall -Wextra -Werror -Ifirmware/robot \
 *         firmware/robot/json_writer.cpp tools/json_writer_test.cpp \
 *         -o build/json_writer_test && ./build/json_writer_test
 */

#include <cstdio>
#include <cstring>
#include <string>

#include "json_writer.h"

namespace {

int g_failures = 0;
int g_checks = 0;

void check(bool condition, const std::string &label) {
  g_checks++;
  if (!condition) {
    g_failures++;
    std::printf("  FAIL  %s\n", label.c_str());
  }
}

void check_equal(const std::string &actual, const std::string &expected, const std::string &label) {
  check(actual == expected, label + " (expected: " + expected + ", got: " + actual + ")");
}

void test_flat_object() {
  char buffer[128];
  jsonw::Writer writer(buffer, sizeof(buffer));
  writer.beginObject();
  writer.field("schema_version", 1L);
  writer.field("active", true);
  writer.field("distance_cm", 31.42, 2);
  writer.field("state", "MONITORING");
  writer.endObject();

  check(writer.ok(), "flat object stays within capacity");
  check_equal(std::string(writer.c_str()),
              "{\"schema_version\":1,\"active\":true,\"distance_cm\":31.42,\"state\":\"MONITORING\"}",
              "flat object serialises correctly");
}

void test_nested_structures() {
  char buffer[256];
  jsonw::Writer writer(buffer, sizeof(buffer));
  writer.beginObject();
  writer.field("device_id", "ESP32-01");
  writer.key("sensors");
  writer.beginObject();
  writer.field("vibration", false);
  writer.field("ir", true);
  writer.field("distance_cm", 18.0, 1);
  writer.endObject();
  writer.key("events");
  writer.beginArray();
  writer.beginObject();
  writer.field("type", "VIBRATION_DETECTED");
  writer.endObject();
  writer.string("EMITTER_ACTIVATED");
  writer.endArray();
  writer.key("notes");
  writer.null();
  writer.endObject();

  check(writer.ok(), "nested payload stays within capacity");
  check_equal(
      std::string(writer.c_str()),
      "{\"device_id\":\"ESP32-01\",\"sensors\":{\"vibration\":false,\"ir\":true,"
      "\"distance_cm\":18.0},\"events\":[{\"type\":\"VIBRATION_DETECTED\"},"
      "\"EMITTER_ACTIVATED\"],\"notes\":null}",
      "nested payload serialises correctly");
}

void test_string_escaping() {
  char buffer[128];
  jsonw::Writer writer(buffer, sizeof(buffer));
  writer.beginObject();
  writer.field("message", "line one\nline \"two\"\ttab\\slash");
  writer.endObject();

  check(writer.ok(), "escaped payload fits");
  check_equal(std::string(writer.c_str()),
              "{\"message\":\"line one\\nline \\\"two\\\"\\ttab\\\\slash\"}",
              "quotes, backslashes and control characters are escaped");
}

void test_control_character_escape() {
  char buffer[64];
  jsonw::Writer writer(buffer, sizeof(buffer));
  writer.beginObject();
  writer.field("m", "a\x01" "b");
  writer.endObject();

  check(writer.ok(), "control character payload fits");
  check_equal(std::string(writer.c_str()), "{\"m\":\"a\\u0001b\"}",
              "control characters use \\u escapes");
}

void test_negative_and_integral_numbers() {
  char buffer[128];
  jsonw::Writer writer(buffer, sizeof(buffer));
  writer.beginObject();
  writer.field("signed", -42L);
  writer.field("delta", -3.5, 2);
  writer.field("zero", 0L);
  writer.field("rounded", 2.345, 1);
  writer.endObject();

  check_equal(std::string(writer.c_str()),
              "{\"signed\":-42,\"delta\":-3.50,\"zero\":0,\"rounded\":2.3}",
              "numbers format without printf float support");
}

void test_overflow_is_reported_and_payload_dropped() {
  char buffer[24];
  jsonw::Writer writer(buffer, sizeof(buffer));
  writer.beginObject();
  writer.field("device_id", "ESP32-01");
  writer.field("schema_version", 1L);

  check(!writer.ok(), "overflow flags the writer as failed");
  check_equal(std::string(writer.c_str()), "", "a failed writer emits nothing rather than broken JSON");
}

void test_size_matches_output() {
  char buffer[128];
  jsonw::Writer writer(buffer, sizeof(buffer));
  writer.beginObject();
  writer.field("a", 1L);
  writer.endObject();

  check(writer.size() == std::strlen(writer.c_str()), "size() matches the emitted string");
}

}  // namespace

int main() {
  test_flat_object();
  test_nested_structures();
  test_string_escaping();
  test_control_character_escape();
  test_negative_and_integral_numbers();
  test_overflow_is_reported_and_payload_dropped();
  test_size_matches_output();

  std::printf("%s  %d checks, %d failures\n", g_failures == 0 ? "PASS" : "FAIL", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
