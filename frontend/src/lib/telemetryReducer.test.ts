import { describe, expect, it } from 'vitest';

import { makeDevice, makeEvent, makePage, makeStatus } from '../test/factories';
import {
  initialTelemetryState,
  MAX_EVENTS_IN_MEMORY,
  mergeEvents,
  telemetryReducer,
  type TelemetryState,
} from './telemetryReducer';
import { matchesFilters } from './filters';

const reduce = (state: TelemetryState, ...actions: Parameters<typeof telemetryReducer>[1][]): TelemetryState =>
  actions.reduce(telemetryReducer, state);

describe('mergeEvents', () => {
  it('drops events already present, whatever their position', () => {
    const existing = [makeEvent({ id: 3 }), makeEvent({ id: 2 })];
    const merged = mergeEvents(existing, [makeEvent({ id: 3 }), makeEvent({ id: 1 })], 'prepend');
    expect(merged.map((event) => event.id)).toEqual([1, 3, 2]);
  });

  it('appends without reordering and honours the memory cap', () => {
    const existing = [makeEvent({ id: 1 })];
    const merged = mergeEvents(existing, [makeEvent({ id: 2 })], 'append', 2);
    expect(merged.map((event) => event.id)).toEqual([1, 2]);
  });

  it('keeps the newest events when the cap is exceeded', () => {
    const existing = Array.from({ length: 3 }, (_, index) => makeEvent({ id: index + 1 }));
    const merged = mergeEvents(existing, [makeEvent({ id: 4 })], 'prepend', 3);
    expect(merged.map((event) => event.id)).toEqual([4, 1, 2]);
  });

  it('returns the same array when there is nothing new', () => {
    const existing = [makeEvent({ id: 1 })];
    expect(mergeEvents(existing, [makeEvent({ id: 1 })], 'prepend')).toBe(existing);
  });

  it('defaults to the in-memory cap', () => {
    const existing = Array.from({ length: MAX_EVENTS_IN_MEMORY }, (_, index) => makeEvent({ id: index + 1 }));
    const merged = mergeEvents(existing, [makeEvent({ id: 9999 })], 'append');
    expect(merged).toHaveLength(MAX_EVENTS_IN_MEMORY);
    expect(merged[merged.length - 1].id).toBe(9999);
  });
});

describe('telemetryReducer', () => {
  it('adopts the status payload on first contact', () => {
    const state = reduce(initialTelemetryState, { type: 'status/success', payload: makeStatus() });
    expect(state.devices).toHaveLength(1);
    expect(state.primaryDeviceId).toBe('ESP32-01');
    expect(state.backendReachable).toBe(true);
    expect(state.lastError).toBeNull();
  });

  it('records an unreachable backend without discarding the last known state', () => {
    const state = reduce(
      initialTelemetryState,
      { type: 'status/success', payload: makeStatus() },
      { type: 'status/failure', message: 'connection refused' },
    );
    expect(state.backendReachable).toBe(false);
    expect(state.lastError).toBe('connection refused');
    expect(state.devices).toHaveLength(1);
  });

  it('replaces devices and merges events from a snapshot frame', () => {
    const state = reduce(
      initialTelemetryState,
      { type: 'ws/snapshot', backend: { websocket: 'connected', websocket_clients: 2, backend: 'online' },
        devices: [makeDevice({ robot_state: 'MONITORING' })], events: [makeEvent({ id: 7 })], serverTime: '2026-03-01T10:00:00Z' },
    );
    expect(state.devices[0].robot_state).toBe('MONITORING');
    expect(state.events.map((event) => event.id)).toEqual([7]);
    expect(state.lastFrameAt).not.toBeNull();
  });

  it('upserts a device from a telemetry frame instead of duplicating it', () => {
    const state = reduce(
      initialTelemetryState,
      { type: 'status/success', payload: makeStatus() },
      { type: 'ws/device', device: makeDevice({ distance_cm: 12.5, robot_state: 'APPROACHING' }) },
    );
    expect(state.devices).toHaveLength(1);
    expect(state.devices[0].distance_cm).toBe(12.5);
  });

  it('inserts a device seen for the first time', () => {
    const state = reduce(initialTelemetryState, {
      type: 'ws/device',
      device: makeDevice({ device_id: 'ESP32-02' }),
    });
    expect(state.devices.map((device) => device.device_id)).toEqual(['ESP32-02']);
    expect(state.primaryDeviceId).toBe('ESP32-02');
  });

  it('tracks history totals without duplicating rows already in memory', () => {
    const state = reduce(
      initialTelemetryState,
      { type: 'ws/events', events: [makeEvent({ id: 1 })] },
      { type: 'events/merge', events: [makeEvent({ id: 1 }), makeEvent({ id: 2 })], total: 42, mode: 'prepend' },
    );
    expect(state.events.map((event) => event.id)).toEqual([2, 1]);
    expect(state.historyTotal).toBe(42);
  });

  it('clears the in-memory log on request', () => {
    const state = reduce(
      initialTelemetryState,
      { type: 'ws/events', events: [makeEvent({ id: 1 })] },
      { type: 'events/clear' },
    );
    expect(state.events).toEqual([]);
    expect(state.historyTotal).toBe(0);
  });

  it('merges filter updates and resets them on clear', () => {
    const filtered = reduce(
      initialTelemetryState,
      { type: 'filters/set', filters: { category: 'EMITTER', search: 'burst' } },
    );
    expect(filtered.filters).toEqual({ category: 'EMITTER', search: 'burst', order: 'desc' });
    expect(reduce(filtered, { type: 'filters/clear' }).filters).toEqual(initialTelemetryState.filters);
  });

  it('selects and clears the inspected event', () => {
    const selected = reduce(initialTelemetryState, { type: 'selection/set', eventId: 5 });
    expect(selected.selectedEventId).toBe(5);
    expect(reduce(selected, { type: 'selection/set', eventId: null }).selectedEventId).toBeNull();
  });

  it('reports the backend stream error verbatim', () => {
    const state = reduce(initialTelemetryState, { type: 'ws/error', message: 'WebSocket closed (code 1006)' });
    expect(state.lastError).toBe('WebSocket closed (code 1006)');
  });

  it('seeds an empty but reachable database as pristine', () => {
    const state = reduce(initialTelemetryState, {
      type: 'status/success',
      payload: makeStatus({ devices: [], device_count: 0, devices_online: 0, primary_device_id: null }),
    });
    expect(state.devices).toHaveLength(0);
    expect(state.backendReachable).toBe(true);
  });

  it('exposes the page payload shape used by the log', () => {
    const page = makePage([makeEvent()], 1);
    expect(page.items).toHaveLength(1);
    expect(page.total).toBe(1);
  });
});

describe('matchesFilters', () => {
  const event = makeEvent();

  it('passes everything when no filter is active', () => {
    expect(matchesFilters(event, { category: 'ALL', search: '', order: 'desc' })).toBe(true);
  });

  it('filters by category', () => {
    expect(matchesFilters(event, { category: 'SENSORS', search: '', order: 'desc' })).toBe(true);
    expect(matchesFilters(event, { category: 'EMITTER', search: '', order: 'desc' })).toBe(false);
  });

  it('searches label, device, message and detail case-insensitively', () => {
    const filters = { category: 'ALL' as const, search: 'VIBRATION', order: 'desc' as const };
    expect(matchesFilters(event, filters)).toBe(true);
    expect(matchesFilters(event, { ...filters, search: 'esp32-01' })).toBe(true);
    expect(matchesFilters(event, { ...filters, search: 'triggered' })).toBe(true);
    expect(matchesFilters(event, { ...filters, search: 'obstacle' })).toBe(false);
  });

  it('ignores surrounding whitespace in the search term', () => {
    expect(matchesFilters(event, { category: 'ALL', search: '   ', order: 'desc' })).toBe(true);
    expect(matchesFilters(event, { category: 'ALL', search: '  vibration  ', order: 'desc' })).toBe(true);
  });
});
