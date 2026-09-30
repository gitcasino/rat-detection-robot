import type {
  DeviceTelemetryState,
  EventPage,
  StatsResponse,
  StatusResponse,
  TelemetryEvent,
} from '../types/telemetry';

export const DEVICE_ID = 'ESP32-01';

export function makeDevice(overrides: Partial<DeviceTelemetryState> = {}): DeviceTelemetryState {
  return {
    device_id: DEVICE_ID,
    label: 'Prototype chassis',
    state: 'ONLINE',
    emitter_active: false,
    emitter_activated_at: null,
    emitter_active_seconds: 0,
    emitter_activations: 0,
    robot_state: 'IDLE',
    distance_cm: 42.5,
    distance_updated_at: '2026-03-01T10:00:00Z',
    vibration: false,
    ir_detected: false,
    wifi_ssid: 'lab-net',
    wifi_rssi: -58,
    ip_address: '192.168.1.42',
    uptime_ms: 3_600_000,
    firmware_version: '1.0.0',
    schema_version: 1,
    first_seen_at: '2026-03-01T09:00:00Z',
    last_seen_at: '2026-03-01T10:00:00Z',
    last_telemetry_at: '2026-03-01T10:00:00Z',
    last_event_at: null,
    offline_since: null,
    offline_count: 0,
    open_session: null,
    ...overrides,
  };
}

export function makeEvent(overrides: Partial<TelemetryEvent> = {}): TelemetryEvent {
  return {
    id: 1,
    device_id: DEVICE_ID,
    event_type: 'VIBRATION_DETECTED',
    category: 'SENSORS',
    source: 'DEVICE',
    occurred_at: '2026-03-01T10:00:00Z',
    received_at: '2026-03-01T10:00:00Z',
    device_timestamp_rejected: false,
    distance_cm: 18.2,
    vibration: true,
    ir_detected: false,
    emitter_active: false,
    robot_state: 'TARGET_DETECTED',
    message: 'Vibration sensor triggered',
    detail: null,
    metadata: { distance_cm: 18.2 },
    emitter_duration_seconds: null,
    ...overrides,
  };
}

export function makeStatus(overrides: Partial<StatusResponse> = {}): StatusResponse {
  return {
    server_time: '2026-03-01T10:00:00Z',
    backend: { websocket: 'connected', websocket_clients: 1, backend: 'online' },
    device_count: 1,
    devices_online: 1,
    devices_offline: 0,
    primary_device_id: DEVICE_ID,
    devices: [makeDevice()],
    ...overrides,
  };
}

export function makePage(items: TelemetryEvent[], total = items.length): EventPage {
  return { items, total, limit: 100, offset: 0 };
}

export function makeStats(overrides: Partial<StatsResponse> = {}): StatsResponse {
  return {
    generated_at: '2026-03-01T10:00:00Z',
    window_hours: 24,
    total_events: 1,
    events_in_window: 1,
    events_by_type: { VIBRATION_DETECTED: 1 },
    events_by_category: { SENSORS: 1 },
    emitter_activations: 2,
    emitter_active_seconds: 42,
    emitter_average_seconds: 21,
    emitter_longest_seconds: 30,
    emitter_open_session: null,
    events_per_bucket: [
      { bucket: '2026-03-01T09:00:00Z', count: 0 },
      { bucket: '2026-03-01T10:00:00Z', count: 1 },
    ],
    devices_by_state: { ONLINE: 1 },
    last_event_at: '2026-03-01T10:00:00Z',
    events_per_hour: { '2026-03-01T10': 1 },
    ...overrides,
  };
}
