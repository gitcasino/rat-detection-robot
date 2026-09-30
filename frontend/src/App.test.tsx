import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TelemetryProvider } from './hooks/TelemetryProvider';
import { DashboardPage } from './pages/DashboardPage';
import { FakeWebSocket, snapshotFrame } from './test/fakeWebSocket';
import { makeDevice, makeEvent, makePage, makeStats, makeStatus } from './test/factories';

const json = (body: unknown): Response => ({ ok: true, status: 200, json: async () => body }) as Response;

function renderDashboard(): void {
  render(
    <TelemetryProvider>
      <DashboardPage />
    </TelemetryProvider>,
  );
}

function statusFetch(
  overrides: Parameters<typeof makeStatus>[0] = {},
  events = [makeEvent({ id: 11, occurred_at: '2026-03-01T10:00:00Z' })],
): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      if (input.includes('/api/status')) {
        return json(makeStatus(overrides));
      }
      if (input.includes('/api/events')) {
        return json(makePage(events));
      }
      if (input.includes('/api/stats')) {
        return json(makeStats());
      }
      if (input.includes('/emitter-sessions')) {
        return json([]);
      }
      return json({});
    }),
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    FakeWebSocket.install();
    statusFetch();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    FakeWebSocket.reset();
  });

  it('renders the live telemetry readouts from the backend payload', async () => {
    renderDashboard();

    expect(await screen.findByText(/Prototype chassis/)).toBeInTheDocument();
    expect(screen.getByText('42.5 cm')).toBeInTheDocument();
    expect(screen.getByText('-58 dBm')).toBeInTheDocument();
    expect(screen.getByText('Idle')).toBeInTheDocument();
    expect(screen.getByText('INACTIVE')).toBeInTheDocument();
  });

  it('shows the stored event log with human labels', async () => {
    renderDashboard();
    const log = await screen.findByRole('log', { name: 'Event log' });
    expect(await within(log).findByText('Vibration')).toBeInTheDocument();
    expect(within(log).getByText('Vibration sensor triggered')).toBeInTheDocument();
  });

  it('applies a snapshot frame pushed over the WebSocket and reaches the live state', async () => {
    renderDashboard();
    await waitFor(() => expect(FakeWebSocket.last).not.toBeNull());

    act(() => {
      FakeWebSocket.last?.openWith(
        snapshotFrame([
          makeDevice({
            emitter_active: true,
            emitter_activated_at: '2026-03-01T09:59:50Z',
            emitter_activations: 3,
            robot_state: 'EMITTER_ACTIVE',
          }),
        ]),
      );
    });

    expect(await screen.findByRole('img', { name: 'Emitter ACTIVE' })).toBeInTheDocument();
    expect(await screen.findByText('Link live')).toBeInTheDocument();
    expect(screen.queryByText('Live stream interrupted')).not.toBeInTheDocument();
    expect(screen.getByText('Emitter active')).toBeInTheDocument();
  });

  it('appends events that arrive as a stream frame', async () => {
    renderDashboard();
    await waitFor(() => expect(FakeWebSocket.last).not.toBeNull());
    act(() => {
      FakeWebSocket.last?.openWith(snapshotFrame([makeDevice()]));
    });

    act(() => {
      FakeWebSocket.last?.emit({
        type: 'events',
        device_id: 'ESP32-01',
        events: [
          makeEvent({
            id: 21,
            event_type: 'EMITTER_ACTIVATED',
            category: 'EMITTER',
            source: 'DEVICE',
            occurred_at: '2026-03-01T10:05:00Z',
            message: 'Emitter command set ACTIVE',
          }),
        ],
      });
    });

    const log = screen.getByRole('log', { name: 'Event log' });
    expect(await within(log).findByText('Emitter activated')).toBeInTheDocument();
    expect(within(log).getByText('Emitter command set ACTIVE')).toBeInTheDocument();
  });

  it('opens the event detail drawer and reports device clock acceptance', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const log = await screen.findByRole('log', { name: 'Event log' });
    await user.click(await within(log).findByRole('button', { name: /Vibration/ }));

    const drawer = await screen.findByRole('dialog');
    expect(within(drawer).getByText('Device clock')).toBeInTheDocument();
    expect(within(drawer).getByText('accepted')).toBeInTheDocument();
    expect(within(drawer).getByText('device reported')).toBeInTheDocument();

    await user.click(within(drawer).getByRole('button', { name: 'Close event detail' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('warns in the detail drawer when the device clock was rejected', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const log = await screen.findByRole('log', { name: 'Event log' });
    await user.click(await within(log).findByRole('button', { name: /Vibration/ }));

    const drawer = await screen.findByRole('dialog');
    // The stored event accepted its clock; the label pair must still be visible.
    expect(within(drawer).getAllByText(/accepted|rejected/).length).toBeGreaterThan(0);
  });

  it('filters the log by category and can clear the filter again', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const log = await screen.findByRole('log', { name: 'Event log' });
    expect(await within(log).findByText('Vibration sensor triggered')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Emitter/ }));
    expect(within(log).queryByText('Vibration sensor triggered')).not.toBeInTheDocument();
    expect(within(log).getByText('No matching events')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Clear filters/ }));
    expect(within(log).getByText('Vibration sensor triggered')).toBeInTheDocument();
  });

  it('searches the log by free text', async () => {
    const user = userEvent.setup();
    renderDashboard();
    await within(await screen.findByRole('log', { name: 'Event log' })).findByText('Vibration sensor triggered');

    await user.type(screen.getByPlaceholderText('filter text'), 'obstacle');
    const log = screen.getByRole('log', { name: 'Event log' });
    expect(within(log).queryByText('Vibration sensor triggered')).not.toBeInTheDocument();
  });

  it('reverses the log order on demand', async () => {
    const user = userEvent.setup();
    renderDashboard();
    const log = await screen.findByRole('log', { name: 'Event log' });
    expect(await within(log).findByText('Vibration sensor triggered')).toBeInTheDocument();

    const orderButton = screen.getByRole('button', { name: /Newest first/ });
    await user.click(orderButton);
    expect(screen.getByRole('button', { name: /Oldest first/ })).toBeInTheDocument();
  });

  it('states plainly that an empty log means no data yet, not missing data', async () => {
    statusFetch({ devices: [], device_count: 0, devices_online: 0, primary_device_id: null }, []);
    renderDashboard();
    await waitFor(() => expect(FakeWebSocket.last).not.toBeNull());
    act(() => {
      FakeWebSocket.last?.openWith(snapshotFrame([]));
    });

    const log = await screen.findByRole('log', { name: 'Event log' });
    expect(await within(log).findByText('No telemetry yet')).toBeInTheDocument();
    expect(within(log).getByText(/nothing is ever fabricated/i)).toBeInTheDocument();
  });

  it('surfaces the emitter as OFFLINE and the device as offline', async () => {
    statusFetch({
      devices: [makeDevice({ state: 'OFFLINE', offline_since: '2026-03-01T09:59:00Z' })],
      devices_online: 0,
      devices_offline: 1,
    });
    renderDashboard();

    expect(await screen.findByRole('img', { name: 'Emitter OFFLINE' })).toBeInTheDocument();
    expect(await screen.findByText('ESP32 offline')).toBeInTheDocument();
    expect(screen.getAllByText('OFFLINE').length).toBeGreaterThan(0);
  });

  it('separates a dropped stream from a dead backend', async () => {
    renderDashboard();
    await waitFor(() => expect(FakeWebSocket.last).not.toBeNull());
    act(() => {
      FakeWebSocket.last?.openWith(snapshotFrame([makeDevice()]));
    });
    expect(await screen.findByText('Link live')).toBeInTheDocument();

    act(() => {
      FakeWebSocket.last?.drop();
    });

    expect(await screen.findByText('Live stream interrupted')).toBeInTheDocument();
    expect(screen.getByText(/reconnect is automatic/i)).toBeInTheDocument();
    expect(screen.queryByText('Backend offline')).not.toBeInTheDocument();
  });

  it('reports a dead backend distinctly from a dropped stream', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );
    renderDashboard();

    const banner = await screen.findByText('Backend offline', { selector: '.banner__title' });
    expect(banner).toBeInTheDocument();
    expect(screen.getByText('Backend offline', { selector: '.link-pill' })).toBeInTheDocument();
  });
});
