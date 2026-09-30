import { formatClockTime, relativeTime } from '../lib/format';
import type { LinkState } from '../types/telemetry';

export interface TopBarProps {
  linkState: LinkState;
  wsStatus: string;
  serverTime: string | null;
  localTime: Date;
  clients: number;
  error: string | null;
  onRefresh: () => void;
}

const LINK_LABEL: Record<LinkState, string> = {
  live: 'Link live',
  degraded: 'Stream degraded',
  offline: 'Backend offline',
};

const LINK_TITLE: Record<LinkState, string> = {
  live: 'WebSocket stream is connected to the backend.',
  degraded: 'Backend reachable, live stream interrupted. Polling fallback is active.',
  offline: 'The dashboard cannot reach the backend. Displayed values may be stale.',
};

export function TopBar({ linkState, wsStatus, serverTime, localTime, clients, error, onRefresh }: TopBarProps) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand__mark">R.A.T.</span>
        <span className="brand__sub">telemetry console</span>
      </div>

      <span
        className="link-pill"
        data-state={linkState}
        title={error ?? LINK_TITLE[linkState]}
        role="status"
        aria-live="polite"
      >
        <span className="link-pill__dot" aria-hidden="true" />
        {LINK_LABEL[linkState]}
        <span className="visually-hidden">, socket {wsStatus}</span>
      </span>

      <span className="app-header__spacer" />

      <div className="app-header__meta">
        <span>
          LOCAL <strong>{formatClockTime(localTime.toISOString())}</strong>
        </span>
        <span>
          SERVER <strong>{serverTime ? formatClockTime(serverTime) : '--:--:--'}</strong>
        </span>
        <span title={serverTime ? `Last update ${relativeTime(serverTime)}` : 'No server contact yet'}>
          CLIENTS <strong>{clients}</strong>
        </span>
        <button type="button" className="action" onClick={onRefresh}>
          Refresh
        </button>
      </div>
    </header>
  );
}
