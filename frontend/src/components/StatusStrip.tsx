import { formatClockTime, relativeTime } from '../lib/format';
import type { DeviceTelemetryState, LinkState, TelemetryEvent } from '../types/telemetry';

export interface StatusStripProps {
  devicesOnline: number;
  devicesOffline: number;
  lastFrameAt: number | null;
  linkState: LinkState;
  eventCount: number;
  primaryDevice: DeviceTelemetryState | null;
  lastEvent: TelemetryEvent | null;
}

export function StatusStrip({
  devicesOnline,
  devicesOffline,
  lastFrameAt,
  linkState,
  eventCount,
  primaryDevice,
  lastEvent,
}: StatusStripProps) {
  const items: Array<{ label: string; value: string; tone?: 'ok' | 'warn' | 'danger' | 'accent'; title?: string }> = [
    {
      label: 'Devices',
      value: `${devicesOnline} online / ${devicesOffline} offline`,
      tone: devicesOnline > 0 ? 'ok' : 'danger',
    },
    {
      label: 'Primary',
      value: primaryDevice ? primaryDevice.device_id : 'none',
      tone: primaryDevice ? undefined : 'warn',
    },
    {
      label: 'Robot',
      value: primaryDevice && primaryDevice.state === 'ONLINE' ? primaryDevice.robot_state : 'OFFLINE',
      tone: primaryDevice && primaryDevice.state === 'ONLINE' ? 'accent' : 'danger',
    },
    {
      label: 'Last event',
      value: lastEvent ? `${formatClockTime(lastEvent.occurred_at)} · ${relativeTime(lastEvent.occurred_at)}` : 'none',
      title: lastEvent?.message ?? undefined,
    },
    {
      label: 'Stream',
      value:
        linkState === 'live'
          ? 'websocket live'
          : linkState === 'degraded'
            ? 'polling fallback'
            : 'no link',
      tone: linkState === 'live' ? 'ok' : linkState === 'degraded' ? 'warn' : 'danger',
      title: lastFrameAt ? `Last frame ${relativeTime(new Date(lastFrameAt).toISOString())}` : 'No frame received yet',
    },
    { label: 'Events in view', value: String(eventCount), tone: undefined },
  ];

  return (
    <ul className="status-strip" aria-label="System status">
      {items.map((item) => (
        <li className="status-strip__item" key={item.label} title={item.title}>
          <span className="status-strip__label">{item.label}</span>
          <span className="status-strip__value" data-tone={item.tone}>
            {item.value}
          </span>
        </li>
      ))}
    </ul>
  );
}
