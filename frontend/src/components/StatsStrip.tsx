import { formatDuration, relativeTime } from '../lib/format';
import type { StatsResponse } from '../types/telemetry';

export interface StatsStripProps {
  stats: StatsResponse | null;
}

export function StatsStrip({ stats }: StatsStripProps) {
  const buckets = stats?.events_per_bucket ?? [];
  const peak = Math.max(1, ...buckets.map((bucket) => bucket.count));

  return (
    <>
      <div className="stats">
        <div className="stat">
          <span className="stat__label">Events {stats ? `${stats.window_hours}h` : ''}</span>
          <span className="stat__value">{stats ? stats.events_in_window : '--'}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Total stored</span>
          <span className="stat__value">{stats ? stats.total_events : '--'}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Emitter activations</span>
          <span className="stat__value" data-tone="accent">
            {stats ? stats.emitter_activations : '--'}
          </span>
        </div>
        <div className="stat">
          <span className="stat__label">Emitter total</span>
          <span className="stat__value">{stats ? formatDuration(stats.emitter_active_seconds) : '--'}</span>
        </div>
        <div className="stat">
          <span className="stat__label">Last event</span>
          <span className="stat__value" style={{ fontSize: 12 }}>
            {stats?.last_event_at ? relativeTime(stats.last_event_at) : 'none'}
          </span>
        </div>
      </div>

      {buckets.length > 0 ? (
        <div className="spark" aria-hidden="true" title={`Event volume across ${buckets.length} buckets`}>
          {buckets.map((bucket) => (
            <span
              key={bucket.bucket}
              className="spark__bar"
              data-tone={bucket.count > 0 ? 'active' : 'idle'}
              style={{ height: `${Math.max(4, Math.round((bucket.count / peak) * 100))}%` }}
            />
          ))}
        </div>
      ) : null}
    </>
  );
}
