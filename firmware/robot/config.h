#pragma once

/*
 * Runtime configuration.
 *
 * Secrets never belong in a committed file. Copy config.example.h to
 * config.local.h (git-ignored) and set the Wi-Fi credentials there; this header
 * is included automatically when the file exists. Without it the firmware still
 * builds and runs - it simply reports a CONFIGURATION ERROR instead of
 * transmitting.
 */

#if defined(__has_include)
#if __has_include("config.local.h")
#include "config.local.h"
#endif
#endif

#include "pins.h"

// --- Identity ----------------------------------------------------------------
#define DEVICE_ID "ESP32-01"
#define DEVICE_LABEL "Rat Detection Robot"
#define FIRMWARE_VERSION "1.0.0"
#define TELEMETRY_SCHEMA_VERSION 1

// --- Wi-Fi (override in config.local.h) -------------------------------------
#ifndef WIFI_SSID
#define WIFI_SSID ""
#endif

#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD ""
#endif

#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 12000
#endif

#ifndef WIFI_RECONNECT_BACKOFF_MIN_MS
#define WIFI_RECONNECT_BACKOFF_MIN_MS 1000
#endif

#ifndef WIFI_RECONNECT_BACKOFF_MAX_MS
#define WIFI_RECONNECT_BACKOFF_MAX_MS 15000
#endif

// --- Backend endpoint (override in config.local.h for a different host) -----
#ifndef BACKEND_HOST
#define BACKEND_HOST "192.168.1.10"
#endif

#ifndef BACKEND_PORT
#define BACKEND_PORT 8000
#endif

#ifndef API_TELEMETRY_PATH
#define API_TELEMETRY_PATH "/api/telemetry"
#endif

#ifndef API_EVENTS_PATH
#define API_EVENTS_PATH "/api/events"
#endif

// Shared secret sent as X-API-Key. Only needed when the backend sets API_KEYS.
#ifndef API_KEY
#define API_KEY ""
#endif

// --- Time synchronisation ---------------------------------------------------
// The server clock is authoritative for stored history. NTP only makes the
// device-side timestamps readable; if it fails, ingest falls back to server time.
#ifndef NTP_SERVER
#define NTP_SERVER "pool.ntp.org"
#endif

#ifndef NTP_UTC_OFFSET_SECONDS
#define NTP_UTC_OFFSET_SECONDS 0
#endif

#ifndef NTP_SYNC_INTERVAL_MS
#define NTP_SYNC_INTERVAL_MS 3600000UL
#endif

// --- Sensor acquisition -----------------------------------------------------
// Preserved from the prototype: an object at or below this distance is treated
// as within interaction range. This is an object-proximity threshold and must
// not be read as species identification.
#define CFG_DETECT_DISTANCE_CM 20.0f

// Hard stop / avoidance threshold. Keep it above CFG_DETECT_DISTANCE_CM so the
// robot can still reach emitter range before it refuses to advance.
#define CFG_OBSTACLE_CLEARANCE_CM 15.0f

// Beyond this distance a reading is treated as unusable for approach decisions.
#define CFG_MAX_USABLE_DISTANCE_CM 400.0f

#define CFG_DISTANCE_SAMPLE_INTERVAL_MS 250UL
#define CFG_ECHO_TIMEOUT_US 25000UL
#define CFG_INVALID_READING_CM -1.0f

// Debounce for the vibration and IR lines. Digital sensor modules chatter.
#define CFG_SENSOR_DEBOUNCE_MS 120UL
#define CFG_SENSOR_ACTIVE_WINDOW_MS 400UL

// --- Target confirmation ----------------------------------------------------
enum TargetConfirmationMode {
  // Vibration and/or IR must agree before activity is declared. Default, and
  // the only mode in which "target activity" means anything beyond proximity.
  TARGET_CONFIRM_FUSION = 0,
  // Prototype behaviour: distance alone declares activity. Useful to exercise
  // the emitter path with only the HC-SR04 wired. Events are tagged accordingly.
  TARGET_CONFIRM_DISTANCE_ONLY = 1,
  // Never declare target activity; the robot monitors and reports only.
  TARGET_CONFIRM_DISABLED = 2,
};

#ifndef CFG_TARGET_CONFIRMATION
#define CFG_TARGET_CONFIRMATION TARGET_CONFIRM_FUSION
#endif

// In fusion mode, require both the vibration and the IR line to agree. The
// default accepts either, which responds faster and tolerates a single failed
// sensor; set true to require corroboration at the cost of missed detections.
#ifndef CFG_REQUIRE_BOTH_CONFIRMATIONS
#define CFG_REQUIRE_BOTH_CONFIRMATIONS false
#endif

// Settling time between declaring activity and starting to move.
#define CFG_TARGET_SETTLE_MS 1500UL

// --- Drive ------------------------------------------------------------------
#define CFG_MOTOR_SPEED_PERCENT 55
#define CFG_TURN_SPEED_PERCENT 45
#define CFG_AVOIDANCE_DURATION_MS 1200UL
// Back away for this long before resuming an approach that was interrupted.
#define CFG_AVOIDANCE_RETRY_MS 4000UL
#define CFG_PWM_MAX 255

// --- Emitter ----------------------------------------------------------------
#define CFG_EMITTER_BURST_MS 3000UL
// Idle period after a burst, during which the emitter cannot re-arm. Prevents
// the transducer from being driven continuously.
#define CFG_EMITTER_COOLDOWN_MS 8000UL
#define CFG_EMITTER_MAX_BURSTS_PER_ACTIVITY 3UL

// --- Telemetry cadence ------------------------------------------------------
#define CFG_TELEMETRY_INTERVAL_MS 1000UL
#define CFG_HEARTBEAT_INTERVAL_MS 2000UL
// Flush buffered events on this cadence even when they are not time critical.
#define CFG_EVENT_FLUSH_INTERVAL_MS 1500UL
#define CFG_HTTP_TIMEOUT_MS 2500

// Set true to persist HEARTBEAT rows. Off by default: presence is already
// tracked through telemetry arrival, so the log stays readable.
#ifndef CFG_EMIT_HEARTBEAT_EVENTS
#define CFG_EMIT_HEARTBEAT_EVENTS false
#endif

// --- Transient buffering ----------------------------------------------------
// RAM only, intentionally: the event log is a record, not a queue that must
// survive power loss. Anything buffered here is lost on reset and that is
// documented behaviour.
#define CFG_EVENT_QUEUE_CAPACITY 48
#define CFG_HTTP_RETRY_BACKOFF_MS 2000
#define CFG_HTTP_RETRY_MAX_MS 20000

// --- Diagnostic serial ------------------------------------------------------
#define CFG_SERIAL_BAUD 115200
