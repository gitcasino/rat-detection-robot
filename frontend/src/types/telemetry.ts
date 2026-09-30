/**
 * Domain types mirroring the backend contract in `backend/app/schemas.py` and
 * `backend/app/domain.py`. Keep the two in step when the event vocabulary changes.
 */

export type EventCategory = 'EMITTER' | 'SENSORS' | 'ROBOT' | 'SYSTEM' | 'ERROR';

export type EventType =
  | 'DEVICE_ONLINE'
  | 'DEVICE_OFFLINE'
  | 'VIBRATION_DETECTED'
  | 'VIBRATION_CLEARED'
  | 'IR_DETECTED'
  | 'IR_CLEARED'
  | 'DISTANCE_UPDATED'
  | 'TARGET_ACTIVITY_DETECTED'
  | 'TARGET_ACTIVITY_CLEARED'
  | 'ROBOT_MOVING'
  | 'ROBOT_STOPPED'
  | 'EMITTER_ACTIVATED'
  | 'EMITTER_DEACTIVATED'
  | 'OBSTACLE_DETECTED'
  | 'OBSTACLE_CLEARED'
  | 'ERROR'
  | 'HEARTBEAT';

export type RobotState =
  | 'IDLE'
  | 'TARGET_DETECTED'
  | 'APPROACHING'
  | 'OBSTACLE_AVOIDANCE'
  | 'EMITTER_ACTIVE'
  | 'MONITORING'
  | 'ERROR';

export type DeviceState = 'ONLINE' | 'OFFLINE';

export type EventSource = 'DEVICE' | 'SERVER';

export interface TelemetryEvent {
  id: number;
  device_id: string;
  event_type: EventType;
  category: EventCategory;
  source: EventSource;
  /** Device clock, or the server clock when the device clock was rejected. */
  occurred_at: string;
  /** Authoritative server receipt time. */
  received_at: string;
  device_timestamp_rejected: boolean;
  distance_cm: number | null;
  vibration: boolean | null;
  ir_detected: boolean | null;
  emitter_active: boolean | null;
  robot_state: RobotState | null;
  message: string | null;
  detail: string | null;
  metadata: Record<string, unknown> | null;
  emitter_duration_seconds: number | null;
}

export interface EmitterSession {
  id: number;
  device_id: string;
  activated_at: string;
  deactivated_at: string | null;
  duration_seconds: number | null;
}

/** Current device state as returned by /api/status and broadcast frames. */
export interface DeviceTelemetryState {
  device_id: string;
  label: string | null;
  state: DeviceState;
  emitter_active: boolean;
  emitter_activated_at: string | null;
  emitter_active_seconds: number;
  emitter_activations: number;
  robot_state: RobotState;
  distance_cm: number | null;
  distance_updated_at: string | null;
  vibration: boolean;
  ir_detected: boolean;
  wifi_ssid: string | null;
  wifi_rssi: number | null;
  ip_address: string | null;
  uptime_ms: number | null;
  firmware_version: string | null;
  schema_version: number;
  first_seen_at: string;
  last_seen_at: string;
  last_telemetry_at: string | null;
  last_event_at: string | null;
  offline_since: string | null;
  offline_count: number;
  open_session: EmitterSession | null;
}

export interface LinkStatus {
  websocket: 'connected' | 'disconnected';
  websocket_clients: number;
  backend: 'online' | 'offline';
}

export interface StatusResponse {
  server_time: string;
  backend: LinkStatus;
  device_count: number;
  devices_online: number;
  devices_offline: number;
  primary_device_id: string | null;
  devices: DeviceTelemetryState[];
}

export interface EventPage {
  items: TelemetryEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  version: string;
  uptime_seconds: number;
  database: 'ok' | 'error';
  server_time: string;
  devices: number;
  devices_online: number;
  websocket_clients: number;
  telemetry_schema_version: number;
}

export interface StatBucket {
  bucket: string;
  count: number;
}

export interface StatsResponse {
  generated_at: string;
  window_hours: number;
  total_events: number;
  events_in_window: number;
  events_by_type: Record<string, number>;
  events_by_category: Record<string, number>;
  emitter_activations: number;
  emitter_active_seconds: number;
  emitter_average_seconds: number | null;
  emitter_longest_seconds: number | null;
  emitter_open_session: EmitterSession | null;
  events_per_bucket: StatBucket[];
  devices_by_state: Record<string, number>;
  last_event_at: string | null;
  events_per_hour: Record<string, number>;
}

/** Emitter presentation state: what the operator actually needs to see at a glance. */
export type EmitterViewState = 'ACTIVE' | 'INACTIVE' | 'OFFLINE';

export type LinkState = 'live' | 'degraded' | 'offline';

export interface EventFilters {
  category: EventCategory | 'ALL';
  search: string;
  order: 'asc' | 'desc';
}
