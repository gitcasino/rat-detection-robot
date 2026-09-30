#include "network.h"

#include <WiFi.h>

#include "config.h"

namespace network {
namespace {

// Anything before 2020 means NTP has not completed, so device timestamps are
// unusable and the server clock is used instead.
constexpr uint32_t MIN_VALID_EPOCH = 1577836800UL;

Status g_status;
uint32_t g_backoff_ms = WIFI_RECONNECT_BACKOFF_MIN_MS;
uint32_t g_next_attempt_ms = 0;
bool g_attempted = false;
uint32_t g_last_ntp_sync_ms = 0;

void start_attempt() {
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  g_attempted = true;
}

void schedule_retry(uint32_t now_ms) {
  g_next_attempt_ms = now_ms + g_backoff_ms;
  // Exponential backoff with a ceiling, so a router that is off does not turn
  // into a retry storm on the radio.
  g_backoff_ms = g_backoff_ms * 2 > WIFI_RECONNECT_BACKOFF_MAX_MS ? WIFI_RECONNECT_BACKOFF_MAX_MS
                                                                 : g_backoff_ms * 2;
}

void sync_time(uint32_t now_ms) {
  if ((now_ms - g_last_ntp_sync_ms) < NTP_SYNC_INTERVAL_MS) {
    return;
  }
  g_last_ntp_sync_ms = now_ms;
  configTime(NTP_UTC_OFFSET_SECONDS, 0, NTP_SERVER);
}

void refresh(uint32_t now_ms) {
  const wl_status_t link = WiFi.status();
  const bool up = link == WL_CONNECTED;
  if (up != g_status.connected) {
    if (up) {
      g_backoff_ms = WIFI_RECONNECT_BACKOFF_MIN_MS;
      sync_time(now_ms);
    } else {
      schedule_retry(now_ms);
    }
  }
  g_status.connected = up;
  g_status.ssid = up ? WiFi.SSID() : String("");
  if (up) {
    g_status.rssi = WiFi.RSSI();
    g_status.ip = WiFi.localIP().toString();
    const uint32_t now_seconds = static_cast<uint32_t>(time(nullptr));
    g_status.clock_valid = now_seconds > MIN_VALID_EPOCH;
  } else {
    g_status.rssi = 0;
    g_status.ip = "";
    g_status.clock_valid = false;
  }
}

}  // namespace

bool credentials_configured() { return strlen(WIFI_SSID) > 0; }

bool begin() {
  g_status = Status();
  g_backoff_ms = WIFI_RECONNECT_BACKOFF_MIN_MS;
  g_next_attempt_ms = 0;
  if (!credentials_configured()) {
    return false;
  }
  start_attempt();
  return true;
}

void tick(uint32_t now_ms) {
  if (!credentials_configured()) {
    return;
  }
  if (g_status.connected || now_ms < g_next_attempt_ms) {
    refresh(now_ms);
    return;
  }
  if (!g_attempted || WiFi.status() == WL_CONNECTED) {
    start_attempt();
    g_next_attempt_ms = now_ms + WIFI_CONNECT_TIMEOUT_MS;
    return;
  }
  if (now_ms >= g_next_attempt_ms) {
    start_attempt();
    g_next_attempt_ms = now_ms + WIFI_CONNECT_TIMEOUT_MS;
  }
  refresh(now_ms);
}

bool connected() { return g_status.connected; }
bool clock_valid() { return g_status.clock_valid; }
const Status &status() { return g_status; }

uint32_t uptime_ms() { return millis(); }

uint32_t epoch_ms() {
  if (!g_status.clock_valid) {
    return 0;
  }
  return static_cast<uint32_t>(time(nullptr)) * 1000UL;
}

String iso8601() {
  if (!g_status.clock_valid) {
    // Empty means "unsynchronised". The server substitutes its own clock and
  // flags the row, which keeps the history honest instead of writing 1970.
    return String("");
  }
  // The UTC offset was applied once through configTime, so no second argument
  // is needed here.
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 5000)) {
    return String("");
  }
  char buffer[32];
  if (strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo) == 0) {
    return String("");
  }
  return String(buffer);
}

}  // namespace network
