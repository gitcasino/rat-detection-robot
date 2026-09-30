#pragma once

/*
 * Example local configuration.
 *
 * Copy this file to config.local.h in the same folder and fill in your own
 * values. config.local.h is git-ignored; never commit real credentials.
 *
 * Windows/macOS/Linux:
 *     cp config.example.h config.local.h
 * Windows PowerShell:
 *     Copy-Item config.example.h config.local.h
 */

#ifndef CONFIG_LOCAL_H
#define CONFIG_LOCAL_H

// Leave the SSID empty to build a firmware image that runs the robot locally
// but reports a configuration error instead of transmitting telemetry.
#define WIFI_SSID ""
#define WIFI_PASSWORD ""

// Hostname or IP of the machine running the backend, on the same LAN.
// A hostname works if the ESP32 can resolve it; an IP always works.
#define BACKEND_HOST "192.168.1.10"
#define BACKEND_PORT 8000

// Only required when the backend is started with API_KEYS set.
#define API_KEY ""

// Shown on the dashboard when the device clock is set.
#define NTP_SERVER "pool.ntp.org"
// Seconds added to UTC for your locale, e.g. 19800 for IST, 3600 for CET.
#define NTP_UTC_OFFSET_SECONDS 0

// Optional per-build overrides, for example to test a different emitter burst.
// #define CFG_EMITTER_BURST_MS 1500UL
// #define CFG_TARGET_CONFIRMATION TARGET_CONFIRM_DISTANCE_ONLY

#endif  // CONFIG_LOCAL_H
