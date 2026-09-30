#include "telemetry.h"

#include <HTTPClient.h>
#include <WiFiClient.h>

#include <string.h>

#include "config.h"
#include "json_writer.h"
#include "robot_network.h"

namespace telemetry {
namespace {

constexpr size_t PAYLOAD_CAPACITY = 1600;
constexpr uint8_t EVENT_BATCH_SIZE = 8;
constexpr size_t MESSAGE_CAPACITY = 48;
constexpr size_t TIMESTAMP_CAPACITY = 24;

struct QueuedEvent {
  EventType type = EventType::Heartbeat;
  uint32_t uptime_ms = 0;
  char timestamp[TIMESTAMP_CAPACITY] = {0};
  float distance_cm = 0.0f;
  int8_t vibration = -1;
  int8_t ir = -1;
  int8_t emitter = -1;
  int8_t robot_state = -1;
  char message[MESSAGE_CAPACITY] = {0};
};

QueuedEvent g_queue[CFG_EVENT_QUEUE_CAPACITY];
uint16_t g_queue_head = 0;
uint16_t g_queue_size = 0;
uint32_t g_dropped = 0;

char g_payload[PAYLOAD_CAPACITY];
uint32_t g_last_telemetry_ms = 0;
uint32_t g_last_event_flush_ms = 0;
uint32_t g_retry_at_ms = 0;
uint32_t g_retry_backoff_ms = CFG_HTTP_RETRY_BACKOFF_MS;
bool g_last_send_ok = false;

void copy_bounded(char *destination, size_t capacity, const char *source) {
  if (source == nullptr) {
    destination[0] = '\0';
    return;
  }
  size_t index = 0;
  while (source[index] != '\0' && index + 1 < capacity) {
    destination[index] = source[index];
    index++;
  }
  destination[index] = '\0';
}

void push(const QueuedEvent &item) {
  if (g_queue_size == CFG_EVENT_QUEUE_CAPACITY) {
    // Drop the oldest entry: the newest transition is the one an operator needs.
    g_queue_head = static_cast<uint16_t>((g_queue_head + 1) % CFG_EVENT_QUEUE_CAPACITY);
    g_queue_size--;
    g_dropped++;
  }
  const uint16_t tail =
      static_cast<uint16_t>((g_queue_head + g_queue_size) % CFG_EVENT_QUEUE_CAPACITY);
  g_queue[tail] = item;
  g_queue_size++;
}

QueuedEvent peek(uint16_t offset) {
  return g_queue[(g_queue_head + offset) % CFG_EVENT_QUEUE_CAPACITY];
}

void pop(uint16_t count) {
  g_queue_head = static_cast<uint16_t>((g_queue_head + count) % CFG_EVENT_QUEUE_CAPACITY);
  g_queue_size = static_cast<uint16_t>(g_queue_size - count);
}

String endpoint(const char *path) {
  String url = "http://";
  url += BACKEND_HOST;
  url += ":";
  url += String(BACKEND_PORT);
  url += path;
  return url;
}

// Returns true when the request completed with a 2xx status.
bool post(const char *path, const char *body, int &status_code) {
  HTTPClient http;
  http.setConnectTimeout(CFG_HTTP_TIMEOUT_MS);
  http.setTimeout(CFG_HTTP_TIMEOUT_MS);
  http.begin(endpoint(path));
  http.addHeader("Content-Type", "application/json");
  if (strlen(API_KEY) > 0) {
    http.addHeader("X-API-Key", API_KEY);
  }
  const int code = http.POST(body);
  status_code = code;
  http.end();
  return code >= 200 && code < 300;
}

void note_send_result(bool ok) {
  g_last_send_ok = ok;
  if (ok) {
    g_retry_backoff_ms = CFG_HTTP_RETRY_BACKOFF_MS;
    return;
  }
  g_retry_backoff_ms = g_retry_backoff_ms * 2 > CFG_HTTP_RETRY_MAX_MS ? CFG_HTTP_RETRY_MAX_MS
                                                                      : g_retry_backoff_ms * 2;
}

void write_event_object(jsonw::Writer &writer, const QueuedEvent &item) {
  writer.beginObject();
  writer.field("type", event_type_name(item.type));
  if (item.timestamp[0] != '\0') {
    writer.field("timestamp", item.timestamp);
  }
  writer.field("uptime_ms", static_cast<unsigned long>(item.uptime_ms));
  writer.field("distance_cm", static_cast<double>(item.distance_cm), 1);
  if (item.vibration >= 0) {
    writer.field("vibration", item.vibration == 1);
  }
  if (item.ir >= 0) {
    writer.field("ir_detected", item.ir == 1);
  }
  if (item.emitter >= 0) {
    writer.field("emitter_active", item.emitter == 1);
  }
  if (item.robot_state >= 0) {
    writer.field("robot_state", robotlogic::Controller::state_name(
                                    static_cast<robotlogic::RobotState>(item.robot_state)));
  }
  if (item.message[0] != '\0') {
    writer.field("message", item.message);
  }
  writer.endObject();
}

bool send_events(uint32_t now_ms) {
  const uint16_t count = g_queue_size < EVENT_BATCH_SIZE ? g_queue_size : EVENT_BATCH_SIZE;
  jsonw::Writer writer(g_payload, sizeof(g_payload));
  writer.beginObject();
  writer.field("schema_version", static_cast<long>(TELEMETRY_SCHEMA_VERSION));
  writer.field("device_id", DEVICE_ID);
  writer.key("events");
  writer.beginArray();
  for (uint16_t index = 0; index < count; index++) {
    write_event_object(writer, peek(index));
  }
  writer.endArray();
  writer.endObject();

  if (!writer.ok()) {
    // A malformed payload must never be sent; the queue stays intact.
    Serial.println(F("[telemetry] payload overflow, event batch withheld"));
    g_retry_at_ms = now_ms + g_retry_backoff_ms;
    return false;
  }

  int status_code = 0;
  const bool ok = post(API_EVENTS_PATH, writer.c_str(), status_code);
  note_send_result(ok);
  if (ok) {
    pop(count);
  } else {
    Serial.print(F("[telemetry] event POST failed status="));
    Serial.println(status_code);
    g_retry_at_ms = now_ms + g_retry_backoff_ms;
  }
  return ok;
}

bool send_telemetry(uint32_t now_ms, const Snapshot &snapshot) {
  jsonw::Writer writer(g_payload, sizeof(g_payload));
  writer.beginObject();
  writer.field("schema_version", static_cast<long>(TELEMETRY_SCHEMA_VERSION));
  writer.field("device_id", DEVICE_ID);
  if (snapshot.clock_valid) {
    writer.field("timestamp", snapshot.timestamp);
  }
  writer.field("uptime_ms", static_cast<unsigned long>(snapshot.uptime_ms));

  writer.key("emitter");
  writer.beginObject();
  writer.field("active", snapshot.emitter_active);
  writer.field("mode", "ULTRASONIC_PULSE");
  writer.field("commanded_by", "firmware");
  writer.endObject();

  writer.key("sensors");
  writer.beginObject();
  writer.field("vibration", snapshot.vibration);
  writer.field("ir", snapshot.ir);
  writer.field("distance_valid", snapshot.distance_valid);
  if (snapshot.distance_valid) {
    writer.field("distance_cm", static_cast<double>(snapshot.distance_cm), 1);
  } else {
    writer.key("distance_cm");
    writer.null();
  }
  writer.field("vibration_configured", snapshot.vibration_configured);
  writer.field("ir_configured", snapshot.ir_configured);
  writer.endObject();

  writer.key("robot");
  writer.beginObject();
  writer.field("state", robotlogic::Controller::state_name(snapshot.robot_state));
  writer.endObject();

  writer.key("network");
  writer.beginObject();
  writer.field("rssi", static_cast<long>(snapshot.rssi));
  writer.field("ip", snapshot.ip);
  writer.field("ssid", snapshot.ssid);
  writer.endObject();

  writer.field("firmware_version", snapshot.firmware_version);
  writer.field("confirmation_mode", snapshot.confirmation_mode_name);
  writer.endObject();

  if (!writer.ok()) {
    Serial.println(F("[telemetry] telemetry payload overflow, frame withheld"));
    g_retry_at_ms = now_ms + g_retry_backoff_ms;
    return false;
  }

  int status_code = 0;
  const bool ok = post(API_TELEMETRY_PATH, writer.c_str(), status_code);
  note_send_result(ok);
  if (!ok) {
    Serial.print(F("[telemetry] telemetry POST failed status="));
    Serial.println(status_code);
    g_retry_at_ms = now_ms + g_retry_backoff_ms;
  }
  return ok;
}

}  // namespace

const char *event_type_name(EventType type) {
  switch (type) {
    case EventType::DeviceOnline:
      return "DEVICE_ONLINE";
    case EventType::VibrationDetected:
      return "VIBRATION_DETECTED";
    case EventType::VibrationCleared:
      return "VIBRATION_CLEARED";
    case EventType::IrDetected:
      return "IR_DETECTED";
    case EventType::IrCleared:
      return "IR_CLEARED";
    case EventType::DistanceUpdated:
      return "DISTANCE_UPDATED";
    case EventType::TargetActivityDetected:
      return "TARGET_ACTIVITY_DETECTED";
    case EventType::TargetActivityCleared:
      return "TARGET_ACTIVITY_CLEARED";
    case EventType::RobotMoving:
      return "ROBOT_MOVING";
    case EventType::RobotStopped:
      return "ROBOT_STOPPED";
    case EventType::EmitterActivated:
      return "EMITTER_ACTIVATED";
    case EventType::EmitterDeactivated:
      return "EMITTER_DEACTIVATED";
    case EventType::ObstacleDetected:
      return "OBSTACLE_DETECTED";
    case EventType::ObstacleCleared:
      return "OBSTACLE_CLEARED";
    case EventType::Error:
      return "ERROR";
    case EventType::Heartbeat:
      return "HEARTBEAT";
  }
  return "ERROR";
}

bool configured() { return strlen(BACKEND_HOST) > 0; }

void begin() {
  g_queue_head = 0;
  g_queue_size = 0;
  g_dropped = 0;
  g_last_telemetry_ms = 0;
  g_last_event_flush_ms = 0;
  g_retry_at_ms = 0;
  g_last_send_ok = false;
}

void record(EventType type, const Snapshot &snapshot, const char *message) {
  QueuedEvent item;
  item.type = type;
  item.uptime_ms = snapshot.uptime_ms;
  item.distance_cm = snapshot.distance_valid ? snapshot.distance_cm : 0.0f;
  item.vibration = snapshot.vibration_configured ? (snapshot.vibration ? 1 : 0) : -1;
  item.ir = snapshot.ir_configured ? (snapshot.ir ? 1 : 0) : -1;
  item.emitter = snapshot.emitter_ready ? (snapshot.emitter_active ? 1 : 0) : -1;
  item.robot_state = static_cast<int8_t>(snapshot.robot_state);
  if (message != nullptr) {
    copy_bounded(item.message, MESSAGE_CAPACITY, message);
  }
  copy_bounded(item.timestamp, TIMESTAMP_CAPACITY, snapshot.timestamp.c_str());
  push(item);
}

void flush(uint32_t now_ms, const Snapshot &snapshot) {
  if (!robot_network::connected() || !configured()) {
    return;
  }
  if (now_ms < g_retry_at_ms) {
    return;
  }

  if (g_queue_size > 0 && (now_ms - g_last_event_flush_ms) >= CFG_EVENT_FLUSH_INTERVAL_MS) {
    g_last_event_flush_ms = now_ms;
    send_events(now_ms);
    return;
  }

  if ((now_ms - g_last_telemetry_ms) >= CFG_TELEMETRY_INTERVAL_MS) {
    g_last_telemetry_ms = now_ms;
    send_telemetry(now_ms, snapshot);
  }
}

uint16_t pending() { return g_queue_size; }
uint32_t dropped() { return g_dropped; }
bool last_send_succeeded() { return g_last_send_ok; }

}  // namespace telemetry
