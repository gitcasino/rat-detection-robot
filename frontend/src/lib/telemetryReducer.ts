/**
 * Pure reducer for the live telemetry state.
 *
 * Kept separate from the provider so the merge rules (especially event
 * de-duplication between the REST snapshot and the WebSocket stream) can be
 * unit tested without React.
 */

import type { SocketStatus } from '../hooks/useWebSocket';
import type {
  DeviceTelemetryState,
  EventFilters,
  LinkStatus,
  StatusResponse,
  TelemetryEvent,
} from '../types/telemetry';

export const MAX_EVENTS_IN_MEMORY = 500;
const MAX_DEVICES = 25;

export interface TelemetryState {
  devices: DeviceTelemetryState[];
  events: TelemetryEvent[];
  backend: LinkStatus;
  deviceCount: number;
  primaryDeviceId: string | null;
  serverTime: string | null;
  wsStatus: SocketStatus;
  backendReachable: boolean;
  lastFrameAt: number | null;
  lastError: string | null;
  historyTotal: number;
  selectedEventId: number | null;
  filters: EventFilters;
}

export const initialTelemetryState: TelemetryState = {
  devices: [],
  events: [],
  backend: { websocket: 'disconnected', websocket_clients: 0, backend: 'online' },
  deviceCount: 0,
  primaryDeviceId: null,
  serverTime: null,
  wsStatus: 'connecting',
  backendReachable: false,
  lastFrameAt: null,
  lastError: null,
  historyTotal: 0,
  selectedEventId: null,
  filters: { category: 'ALL', search: '', order: 'desc' },
};

export type TelemetryAction =
  | { type: 'status/success'; payload: StatusResponse }
  | { type: 'status/failure'; message: string }
  | { type: 'ws/status'; status: SocketStatus }
  | { type: 'ws/error'; message: string | null }
  | {
      type: 'ws/snapshot';
      backend: LinkStatus;
      devices: DeviceTelemetryState[];
      events: TelemetryEvent[];
      serverTime: string | null;
    }
  | { type: 'ws/device'; device: DeviceTelemetryState }
  | { type: 'ws/events'; events: TelemetryEvent[] }
  | { type: 'ws/serverTime'; serverTime: string | null }
  | { type: 'events/merge'; events: TelemetryEvent[]; total?: number; mode: 'prepend' | 'append' }
  | { type: 'events/clear' }
  | { type: 'selection/set'; eventId: number | null }
  | { type: 'filters/set'; filters: Partial<EventFilters> }
  | { type: 'filters/clear' };

function upsertDevice(devices: DeviceTelemetryState[], device: DeviceTelemetryState): DeviceTelemetryState[] {
  const index = devices.findIndex((candidate) => candidate.device_id === device.device_id);
  if (index === -1) {
    return [...devices, device].slice(0, MAX_DEVICES);
  }
  const next = devices.slice();
  next[index] = device;
  return next;
}

export function mergeEvents(
  existing: TelemetryEvent[],
  incoming: TelemetryEvent[],
  mode: 'prepend' | 'append',
  limit = MAX_EVENTS_IN_MEMORY,
): TelemetryEvent[] {
  const known = new Set(existing.map((event) => event.id));
  const fresh = incoming.filter((event) => !known.has(event.id));
  if (fresh.length === 0) {
    return existing;
  }
  if (mode === 'append') {
    return [...existing, ...fresh].slice(-limit);
  }
  // Newest first, so a prepend keeps the newest event at the top of the log.
  return [...fresh.reverse(), ...existing].slice(0, limit);
}

function sortNewestFirst(events: TelemetryEvent[]): TelemetryEvent[] {
  return [...events].sort((left, right) => right.id - left.id);
}

export function telemetryReducer(state: TelemetryState, action: TelemetryAction): TelemetryState {
  switch (action.type) {
    case 'status/success': {
      const payload = action.payload;
      return {
        ...state,
        devices: payload.devices,
        deviceCount: payload.device_count,
        primaryDeviceId: payload.primary_device_id ?? payload.devices[0]?.device_id ?? null,
        backend: payload.backend,
        serverTime: payload.server_time,
        backendReachable: true,
        lastError: null,
      };
    }
    case 'status/failure':
      return { ...state, backendReachable: false, lastError: action.message };
    case 'ws/status':
      return { ...state, wsStatus: action.status };
    case 'ws/error':
      return { ...state, lastError: action.message };
    case 'ws/snapshot': {
      return {
        ...state,
        devices: action.devices,
        backend: action.backend,
        serverTime: action.serverTime ?? state.serverTime,
        primaryDeviceId: action.devices[0]?.device_id ?? state.primaryDeviceId,
        deviceCount: action.devices.length,
        backendReachable: true,
        lastFrameAt: Date.now(),
        events: mergeEvents(state.events, sortNewestFirst(action.events), 'prepend'),
      };
    }
    case 'ws/device': {
      const devices = upsertDevice(state.devices, action.device);
      return {
        ...state,
        devices,
        lastFrameAt: Date.now(),
        deviceCount: devices.length,
        primaryDeviceId: state.primaryDeviceId ?? action.device.device_id,
      };
    }
    case 'ws/events':
      return { ...state, events: mergeEvents(state.events, action.events, 'prepend'), lastFrameAt: Date.now() };
    case 'ws/serverTime':
      return { ...state, serverTime: action.serverTime ?? state.serverTime };
    case 'events/merge':
      return {
        ...state,
        events: mergeEvents(state.events, action.events, action.mode),
        historyTotal: action.total ?? state.historyTotal,
        backendReachable: true,
      };
    case 'events/clear':
      return { ...state, events: [], historyTotal: 0 };
    case 'selection/set':
      return { ...state, selectedEventId: action.eventId };
    case 'filters/set':
      return { ...state, filters: { ...state.filters, ...action.filters } };
    case 'filters/clear':
      return { ...state, filters: initialTelemetryState.filters };
    default:
      return state;
  }
}
