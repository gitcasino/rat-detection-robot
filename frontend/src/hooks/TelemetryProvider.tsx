/**
 * Store provider: one WebSocket, a slow REST safety net, and the derived state
 * the dashboard renders.
 *
 * The WebSocket is the primary channel. REST polling only exists so the console
 * keeps working when the stream is blocked by a proxy, and to seed the first
 * paint. Nothing here invents data: every value comes from the backend.
 */

import { useCallback, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react';

import { getEvents, getStatus, type EventQuery } from '../lib/api';
import { matchesFilters } from '../lib/filters';
import { initialTelemetryState, telemetryReducer } from '../lib/telemetryReducer';
import type { ServerFrame } from '../types/frames';
import { useWebSocket, type SocketStatus } from './useWebSocket';
import { emitterViewState, linkStateOf, TelemetryContext, type TelemetryStore } from './telemetryContext';

const STATUS_POLL_MS = 20000;
const HISTORY_PAGE_SIZE = 100;

export interface TelemetryProviderProps {
  children: ReactNode;
  /** Test seam: skips the network entirely. */
  enabled?: boolean;
  pollIntervalMs?: number;
}

export function TelemetryProvider({ children, enabled = true, pollIntervalMs = STATUS_POLL_MS }: TelemetryProviderProps) {
  const [state, dispatch] = useReducer(telemetryReducer, initialTelemetryState);
  const frameHandlerRef = useRef<(frame: ServerFrame) => void>(() => undefined);

  const handleFrame = useCallback((frame: ServerFrame) => {
    frameHandlerRef.current(frame);
  }, []);

  const { lastError: wsError } = useWebSocket({
    enabled,
    onFrame: handleFrame,
    onStatusChange: (status: SocketStatus) => dispatch({ type: 'ws/status', status }),
  });

  // Latest-frame handling; split out so the reducer stays the single merge path.
  useEffect(() => {
    frameHandlerRef.current = (frame: ServerFrame): void => {
      if (frame.type === 'snapshot') {
        dispatch({
          type: 'ws/snapshot',
          backend: frame.backend,
          devices: frame.devices,
          events: frame.events ?? [],
          serverTime: frame.server_time ?? null,
        });
        return;
      }
      if (frame.type === 'telemetry' || frame.type === 'device') {
        dispatch({ type: 'ws/device', device: frame.device });
        return;
      }
      if (frame.type === 'events') {
        dispatch({ type: 'ws/events', events: frame.events ?? [] });
        return;
      }
      if (frame.type === 'error') {
        dispatch({ type: 'ws/error', message: frame.detail ?? 'Backend reported a stream error' });
        return;
      }
      if (frame.server_time) {
        dispatch({ type: 'ws/serverTime', serverTime: frame.server_time });
      }
    };
  }, []);

  useEffect(() => {
    if (wsError) {
      dispatch({ type: 'ws/error', message: wsError });
    }
  }, [wsError]);

  const refreshStatus = useCallback((): (() => void) | void => {
    if (!enabled) {
      return undefined;
    }
    const controller = new AbortController();
    void getStatus(controller.signal)
      .then((payload) => dispatch({ type: 'status/success', payload }))
      .catch((error: unknown) => {
        dispatch({
          type: 'status/failure',
          message: error instanceof Error ? error.message : 'Backend unreachable',
        });
      });
    return () => controller.abort();
  }, [enabled]);

  useEffect(() => {
    const cleanup = refreshStatus();
    if (!enabled) {
      return undefined;
    }
    const timer = setInterval(() => {
      refreshStatus();
    }, pollIntervalMs);
    return () => {
      clearInterval(timer);
      cleanup?.();
    };
  }, [refreshStatus, pollIntervalMs, enabled]);

  const loadHistory = useCallback(
    async (query: EventQuery = {}) => {
      if (!enabled) {
        return;
      }
      try {
        const page = await getEvents({ limit: HISTORY_PAGE_SIZE, order: 'desc', ...query });
        dispatch({ type: 'events/merge', events: page.items, total: page.total, mode: 'prepend' });
      } catch (error) {
        dispatch({
          type: 'ws/error',
          message: error instanceof Error ? error.message : 'History request failed',
        });
      }
    },
    [enabled],
  );

  // Load history once at start-up so the log is useful before the first frame.
  useEffect(() => {
    if (enabled) {
      void loadHistory();
    }
  }, [enabled, loadHistory]);

  const primaryDevice = useMemo(
    () => state.devices.find((device) => device.device_id === state.primaryDeviceId) ?? state.devices[0] ?? null,
    [state.devices, state.primaryDeviceId],
  );

  const filteredEvents = useMemo(() => {
    const visible = state.events.filter((event) => matchesFilters(event, state.filters));
    return state.filters.order === 'desc' ? visible : [...visible].reverse();
  }, [state.events, state.filters]);

  const devicesOnline = useMemo(() => state.devices.filter((device) => device.state === 'ONLINE').length, [state.devices]);
  const devicesOffline = useMemo(
    () => state.devices.filter((device) => device.state === 'OFFLINE').length,
    [state.devices],
  );

  const store = useMemo<TelemetryStore>(
    () => ({
      state,
      primaryDevice,
      emitterState: emitterViewState(primaryDevice),
      linkState: linkStateOf(state),
      devicesOnline,
      devicesOffline,
      filteredEvents,
      isPristine: state.devices.length === 0 && state.historyTotal === 0 && state.backendReachable,
      setFilter: (filters) => dispatch({ type: 'filters/set', filters }),
      clearFilters: () => dispatch({ type: 'filters/clear' }),
      selectEvent: (eventId) => dispatch({ type: 'selection/set', eventId }),
      refresh: () => {
        refreshStatus();
        void loadHistory();
      },
      loadHistory,
    }),
    [state, primaryDevice, devicesOnline, devicesOffline, filteredEvents, refreshStatus, loadHistory],
  );

  return <TelemetryContext.Provider value={store}>{children}</TelemetryContext.Provider>;
}
