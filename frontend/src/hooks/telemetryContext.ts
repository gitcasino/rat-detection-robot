/**
 * Telemetry store contract.
 *
 * The context object, its types and the consumer hook live here so that
 * `TelemetryProvider.tsx` exports a single React component (which keeps Vite's
 * fast-refresh working during development).
 */

import { createContext, useContext } from 'react';

import type { EventQuery } from '../lib/api';
import type { TelemetryState } from '../lib/telemetryReducer';
import type {
  DeviceTelemetryState,
  EmitterViewState,
  EventFilters,
  LinkState,
  TelemetryEvent,
} from '../types/telemetry';

export interface TelemetryStore {
  state: TelemetryState;
  primaryDevice: DeviceTelemetryState | null;
  emitterState: EmitterViewState;
  linkState: LinkState;
  devicesOnline: number;
  devicesOffline: number;
  filteredEvents: TelemetryEvent[];
  isPristine: boolean;
  setFilter: (filters: Partial<EventFilters>) => void;
  clearFilters: () => void;
  selectEvent: (eventId: number | null) => void;
  refresh: () => void;
  loadHistory: (query?: EventQuery) => Promise<void>;
}

export const TelemetryContext = createContext<TelemetryStore | null>(null);

export function useTelemetryStore(): TelemetryStore {
  const store = useContext(TelemetryContext);
  if (!store) {
    throw new Error('useTelemetryStore must be used inside <TelemetryProvider>');
  }
  return store;
}

export function emitterViewState(device: DeviceTelemetryState | null): EmitterViewState {
  if (!device || device.state === 'OFFLINE') {
    return 'OFFLINE';
  }
  return device.emitter_active ? 'ACTIVE' : 'INACTIVE';
}

export function linkStateOf(state: TelemetryState): LinkState {
  if (!state.backendReachable) {
    return 'offline';
  }
  return state.wsStatus === 'open' ? 'live' : 'degraded';
}
