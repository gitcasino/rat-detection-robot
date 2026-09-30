import { useCallback, useEffect, useMemo, useState } from 'react';
import { Cpu, Layers, LineChart } from 'lucide-react';

import { DeviceList } from '../components/DeviceList';
import { EmitterPanel } from '../components/EmitterPanel';
import { EventDetail } from '../components/EventDetail';
import { EventStream } from '../components/EventStream';
import { Panel } from '../components/Panel';
import { StatsStrip } from '../components/StatsStrip';
import { StatusBanner } from '../components/StatusBanner';
import { StatusStrip } from '../components/StatusStrip';
import { TelemetryGrid } from '../components/TelemetryGrid';
import { TopBar } from '../components/TopBar';
import { useClock } from '../hooks/useClock';
import { useTelemetryStore } from '../hooks/telemetryContext';
import { getStats, type EventQuery } from '../lib/api';
import type { StatsResponse } from '../types/telemetry';

const STATS_POLL_MS = 60000;

export function DashboardPage() {
  const store = useTelemetryStore();
  const localTime = useClock();
  const [stats, setStats] = useState<StatsResponse | null>(null);

  const { state, primaryDevice, filteredEvents, emitterState, linkState } = store;

  const selectedEvent = useMemo(
    () => state.events.find((event) => event.id === state.selectedEventId) ?? null,
    [state.events, state.selectedEventId],
  );

  const lastEvent = state.events.length > 0 ? state.events[0] : null;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const load = (): void => {
      void getStats(24, controller.signal)
        .then((payload) => {
          if (active) {
            setStats(payload);
          }
        })
        .catch(() => undefined);
    };
    load();
    const timer = setInterval(load, STATS_POLL_MS);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  const onExport = useCallback(() => {
    const payload = JSON.stringify(
      {
        exported_at: new Date().toISOString(),
        device_id: primaryDevice?.device_id ?? null,
        filters: state.filters,
        events: filteredEvents,
      },
      null,
      2,
    );
    const blob = new Blob([payload], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `rat-telemetry-${primaryDevice?.device_id ?? 'all'}-${Date.now()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [filteredEvents, primaryDevice?.device_id, state.filters]);

  const loadHistoryForDevice = useCallback(
    (query: EventQuery) => {
      void store.loadHistory({ deviceId: primaryDevice?.device_id, ...query });
    },
    [store, primaryDevice?.device_id],
  );

  return (
    <div className="app-shell">
      <TopBar
        linkState={linkState}
        wsStatus={state.wsStatus}
        serverTime={state.serverTime}
        localTime={localTime}
        clients={state.backend.websocket_clients}
        error={state.lastError}
        onRefresh={store.refresh}
      />

      <StatusStrip
        devicesOnline={store.devicesOnline}
        devicesOffline={store.devicesOffline}
        lastFrameAt={state.lastFrameAt}
        linkState={linkState}
        eventCount={filteredEvents.length}
        primaryDevice={primaryDevice}
        lastEvent={lastEvent}
      />

      <StatusBanner
        linkState={linkState}
        error={state.lastError}
        devicesOffline={store.devicesOffline}
        deviceOfflineSince={primaryDevice?.offline_since ?? null}
      />

      <main className="dashboard">
        <div className="dashboard__column">
          <Panel title="Emitter command state" variant="emitter" aside="server-authoritative">
            <EmitterPanel
              device={primaryDevice}
              emitterState={emitterState}
              stats={stats}
              pristine={store.isPristine}
            />
          </Panel>

          <Panel
            title="Live telemetry"
            flush
            aside={primaryDevice ? primaryDevice.device_id : 'no device'}
          >
            <TelemetryGrid device={primaryDevice} wsConnected={linkState === 'live'} />
          </Panel>

          <Panel
            title="Activity volume"
            flush
            aside={stats ? `last ${stats.window_hours}h` : 'loading'}
          >
            <StatsStrip stats={stats} />
          </Panel>
        </div>

        <div className="dashboard__column">
          <Panel
            title="Event log"
            variant="log"
            flush
            aside={`${state.historyTotal} stored`}
          >
            <EventStream
              events={filteredEvents}
              filters={state.filters}
              historyTotal={state.historyTotal}
              selectedEventId={state.selectedEventId}
              pristine={store.isPristine}
              linkState={linkState}
              onFilterChange={store.setFilter}
              onClearFilters={store.clearFilters}
              onSelect={store.selectEvent}
              onRefresh={() => loadHistoryForDevice({})}
              onExport={onExport}
            />
          </Panel>

          <Panel
            title="Devices"
            flush
            aside={
              <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                <Cpu size={11} aria-hidden="true" />
                <Layers size={11} aria-hidden="true" />
                <LineChart size={11} aria-hidden="true" />
              </span>
            }
          >
            {state.devices.length === 0 ? (
              <p className="empty__detail" style={{ padding: '14px 12px' }}>
                No devices have reported yet. A device appears here the moment it posts its first telemetry payload.
              </p>
            ) : (
              <DeviceList
                devices={state.devices}
                selectedDeviceId={primaryDevice?.device_id ?? null}
                onSelect={(deviceId) => {
                  void store.loadHistory({ deviceId });
                }}
              />
            )}
          </Panel>
        </div>
      </main>

      <footer className="app-footer">
        <span>Smart Rat Detection and Repellent Robot</span>
        <span>esp32 → fastapi → react</span>
        <span className="app-footer__spacer" />
        <span>telemetry schema v{primaryDevice?.schema_version ?? 1}</span>
        <span>no synthetic data</span>
      </footer>

      <EventDetail event={selectedEvent} onClose={() => store.selectEvent(null)} />
    </div>
  );
}
