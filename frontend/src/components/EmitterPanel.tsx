import { useEffect, useMemo, useState } from 'react';
import { Activity, Info, Radio } from 'lucide-react';

import { useElapsedSeconds } from '../hooks/useElapsedSeconds';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { formatClockTime, formatDuration } from '../lib/format';
import type { DeviceTelemetryState, EmitterViewState, StatsResponse } from '../types/telemetry';

export interface EmitterPanelProps {
  device: DeviceTelemetryState | null;
  emitterState: EmitterViewState;
  stats: StatsResponse | null;
  pristine: boolean;
}

const BAR_COUNT = 26;

const STATE_COPY: Record<EmitterViewState, { label: string; sub: string }> = {
  ACTIVE: { label: 'ACTIVE', sub: 'command asserted' },
  INACTIVE: { label: 'INACTIVE', sub: 'command released' },
  OFFLINE: { label: 'OFFLINE', sub: 'device unreachable' },
};

function barLevel(index: number, phase: number): 'high' | 'mid' | 'low' {
  const value = Math.abs(Math.sin(phase + index * 0.55) * Math.cos(phase * 0.7 + index * 0.21));
  if (value > 0.66) {
    return 'high';
  }
  return value > 0.33 ? 'mid' : 'low';
}

export function EmitterPanel({ device, emitterState, stats, pristine }: EmitterPanelProps) {
  const reducedMotion = usePrefersReducedMotion();
  const active = emitterState === 'ACTIVE';
  const elapsed = useElapsedSeconds(device?.emitter_activated_at ?? null, active);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (!active || reducedMotion) {
      return undefined;
    }
    const timer = setInterval(() => setPhase((value) => value + 0.28), 90);
    return () => clearInterval(timer);
  }, [active, reducedMotion]);

  const bars = useMemo(
    () => Array.from({ length: BAR_COUNT }, (_, index) => (active && !reducedMotion ? barLevel(index, phase) : 'low')),
    [active, phase, reducedMotion],
  );

  const copy = STATE_COPY[emitterState];
  const statsBody = [
    { label: 'Active for', value: active ? formatDuration(elapsed) : '--' },
    { label: 'Activations', value: device ? String(device.emitter_activations) : '--' },
    { label: 'Average', value: stats?.emitter_average_seconds != null ? formatDuration(stats.emitter_average_seconds) : '--' },
    { label: 'Longest', value: stats?.emitter_longest_seconds != null ? formatDuration(stats.emitter_longest_seconds) : '--' },
  ];

  return (
    <div className="emitter" data-state={emitterState}>
      <div className="emitter__top">
        <div className="emitter__dial" data-state={emitterState} role="img" aria-label={`Emitter ${copy.label}`}>
          <span className="emitter__wave" aria-hidden="true" />
          <span className="emitter__wave" aria-hidden="true" />
          <span className="emitter__dial-label">
            <span className="emitter__state">{copy.label}</span>
            <span className="emitter__dial-sub">{copy.sub}</span>
          </span>
        </div>

        <div className="panel__body" style={{ padding: 0 }}>
          <div className="emitter__bars" aria-hidden="true">
            {bars.map((level, index) => (
              <span
                // Index is a stable identity for a fixed-length array.
                key={index}
                className="emitter__bar"
                data-level={level}
                style={{ height: `${level === 'high' ? 100 : level === 'mid' ? 62 : 28}%` }}
              />
            ))}
          </div>
          <p className="emitter__note" style={{ marginTop: 12 }}>
            <Info size={13} aria-hidden="true" style={{ flex: '0 0 auto', marginTop: 1 }} />
            <span>
              Command state only. There is no acoustic feedback circuit, so this panel cannot confirm that sound was
              produced. A session opens when the command turns on and closes when it turns off.
            </span>
          </p>
        </div>
      </div>

      <div className="emitter__stats">
        {statsBody.map((item) => (
          <div className="emitter__stat" key={item.label}>
            <span className="emitter__stat-label">{item.label}</span>
            <span className="emitter__stat-value">{item.value}</span>
          </div>
        ))}
      </div>

      <div className="emitter__note">
        <Radio size={13} aria-hidden="true" style={{ flex: '0 0 auto', marginTop: 1 }} />
        <span>
          {pristine
            ? 'No activation recorded yet.'
            : active && device
              ? `Command asserted at ${formatClockTime(device.emitter_activated_at)}.`
              : device
                ? `Last reported ${formatClockTime(device.last_seen_at)}.`
                : 'Waiting for the first device state.'}
          {stats && stats.emitter_activations > 0 ? ` ${stats.emitter_activations} activations in the last ${stats.window_hours}h.` : ''}
        </span>
        {active ? <Activity size={13} aria-hidden="true" style={{ color: 'var(--alert)' }} /> : null}
      </div>
    </div>
  );
}
