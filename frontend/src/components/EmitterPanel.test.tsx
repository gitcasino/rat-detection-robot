import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EmitterPanel } from './EmitterPanel';
import { makeDevice } from '../test/factories';
import type { EmitterViewState } from '../types/telemetry';

const stats = {
  generated_at: '2026-03-01T10:00:00Z',
  window_hours: 24,
  total_events: 10,
  events_in_window: 10,
  events_by_type: {},
  events_by_category: {},
  emitter_activations: 4,
  emitter_active_seconds: 96,
  emitter_average_seconds: 24,
  emitter_longest_seconds: 30,
  emitter_open_session: null,
  events_per_bucket: [],
  devices_by_state: { ONLINE: 1 },
  last_event_at: '2026-03-01T10:00:00Z',
  events_per_hour: {},
};

describe('EmitterPanel', () => {
  it('reports INACTIVE and refuses to imply acoustic output', () => {
    render(<EmitterPanel device={makeDevice()} emitterState="INACTIVE" stats={stats} pristine={false} />);

    expect(screen.getByText('INACTIVE')).toBeInTheDocument();
    expect(screen.getByText(/command released/i)).toBeInTheDocument();
    expect(screen.getByText(/cannot confirm that sound was produced/i)).toBeInTheDocument();
  });

  it('shows ACTIVE with the running session and aggregate statistics', () => {
    render(
      <EmitterPanel
        device={makeDevice({ emitter_active: true, emitter_activated_at: '2026-03-01T09:59:30Z', emitter_activations: 4 })}
        emitterState="ACTIVE"
        stats={stats}
        pristine={false}
      />,
    );

    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('24s')).toBeInTheDocument();
    expect(screen.getByText('30s')).toBeInTheDocument();
    expect(screen.getByText(/command asserted at/i)).toBeInTheDocument();
  });

  it('labels the emitter OFFLINE with no device', () => {
    render(<EmitterPanel device={null} emitterState="OFFLINE" stats={null} pristine />);

    expect(screen.getByText('OFFLINE')).toBeInTheDocument();
    expect(screen.getByText('device unreachable')).toBeInTheDocument();
    expect(screen.getByText('No activation recorded yet.')).toBeInTheDocument();
  });

  it.each<[EmitterViewState, RegExp]>([
    ['ACTIVE', /command asserted/i],
    ['INACTIVE', /command released/i],
    ['OFFLINE', /device unreachable/i],
  ])('announces %s to assistive technology', (state, expected) => {
    render(<EmitterPanel device={null} emitterState={state} stats={null} pristine />);
    expect(screen.getByRole('img', { name: `Emitter ${state}` })).toBeInTheDocument();
    expect(screen.getAllByText(expected).length).toBeGreaterThan(0);
  });
});
