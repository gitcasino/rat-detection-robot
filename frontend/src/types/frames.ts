/** Server -> browser frames. See `backend/app/api/stream.py` for the contract. */

import type { DeviceTelemetryState, LinkStatus, TelemetryEvent } from './telemetry';

interface BaseFrame {
  server_time?: string;
}

export interface SnapshotFrame extends BaseFrame {
  type: 'snapshot';
  backend: LinkStatus;
  devices: DeviceTelemetryState[];
  events: TelemetryEvent[];
  device_filter: string | null;
}

export interface TelemetryFrame extends BaseFrame {
  type: 'telemetry';
  device: DeviceTelemetryState;
}

export interface EventsFrame extends BaseFrame {
  type: 'events';
  device_id: string;
  events: TelemetryEvent[];
}

export interface DeviceFrame extends BaseFrame {
  type: 'device';
  device: DeviceTelemetryState;
}

export interface PongFrame extends BaseFrame {
  type: 'pong';
}

export interface ErrorFrame extends BaseFrame {
  type: 'error';
  detail?: string;
}

export type ServerFrame = SnapshotFrame | TelemetryFrame | EventsFrame | DeviceFrame | PongFrame | ErrorFrame;

export function isServerFrame(value: unknown): value is ServerFrame {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const type = (value as { type?: unknown }).type;
  return (
    type === 'snapshot' ||
    type === 'telemetry' ||
    type === 'events' ||
    type === 'device' ||
    type === 'pong' ||
    type === 'error'
  );
}
