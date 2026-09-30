import type { ReactNode } from 'react';
import { Activity, Radar, RadioTower, Route, ScanLine, Waves } from 'lucide-react';

import {
  formatBoolean,
  formatDistance,
  formatSigned,
  formatUptime,
  relativeTime,
} from '../lib/format';
import { ROBOT_STATE_LABEL } from '../lib/eventMeta';
import type { DeviceTelemetryState } from '../types/telemetry';

export interface TelemetryGridProps {
  device: DeviceTelemetryState | null;
  wsConnected: boolean;
}

interface ReadoutSpec {
  key: string;
  label: string;
  icon: ReactNode;
  value: string;
  sub: string;
  tone?: Tone;
  barPercent?: number;
  active?: boolean;
  offline?: boolean;
}

const OFFLINE_VALUE = '--';

function distanceTone(distanceCm: number | null | undefined, detectionCm = 20): 'ok' | 'warn' | 'accent' | undefined {
  if (distanceCm === null || distanceCm === undefined) {
    return undefined;
  }
  if (distanceCm <= detectionCm) {
    return 'warn';
  }
  if (distanceCm <= 60) {
    return 'accent';
  }
  return 'ok';
}

type Tone = 'ok' | 'warn' | 'danger' | 'accent';

const ROBOT_TONES: Record<string, Tone | undefined> = {
  IDLE: undefined,
  TARGET_DETECTED: 'warn',
  APPROACHING: 'accent',
  OBSTACLE_AVOIDANCE: 'warn',
  EMITTER_ACTIVE: 'accent',
  MONITORING: 'ok',
  ERROR: 'danger',
};

function robotTone(robotState: string | undefined): Tone | undefined {
  return robotState ? ROBOT_TONES[robotState] : undefined;
}

export function TelemetryGrid({ device, wsConnected }: TelemetryGridProps) {
  const offline = !device || device.state === 'OFFLINE';
  const readouts: ReadoutSpec[] = [
    {
      key: 'distance',
      label: 'Distance',
      icon: <Radar size={13} aria-hidden="true" />,
      value: offline ? OFFLINE_VALUE : formatDistance(device.distance_cm),
      sub: offline ? 'no reading' : `last sample ${relativeTime(device.distance_updated_at)}`,
      tone: distanceTone(device?.distance_cm),
      barPercent:
        device?.distance_cm && device.distance_cm > 0 ? Math.min(100, Math.round((device.distance_cm / 120) * 100)) : 0,
    },
    {
      key: 'vibration',
      label: 'Vibration',
      icon: <Waves size={13} aria-hidden="true" />,
      value: offline ? OFFLINE_VALUE : formatBoolean(device.vibration),
      sub: offline ? 'sensor offline' : 'piezo / contact channel',
      tone: !offline && device.vibration ? 'warn' : undefined,
      active: !offline && device.vibration,
    },
    {
      key: 'ir',
      label: 'Infrared',
      icon: <ScanLine size={13} aria-hidden="true" />,
      value: offline ? OFFLINE_VALUE : formatBoolean(device.ir_detected),
      sub: offline ? 'sensor offline' : 'beam-break channel',
      tone: !offline && device.ir_detected ? 'accent' : undefined,
      active: !offline && device.ir_detected,
    },
    {
      key: 'robot',
      label: 'Robot state',
      icon: <Route size={13} aria-hidden="true" />,
      value: offline ? OFFLINE_VALUE : (ROBOT_STATE_LABEL[device.robot_state] ?? device.robot_state),
      sub: offline ? 'device offline' : device.robot_state,
      tone: offline ? 'danger' : robotTone(device.robot_state),
    },
    {
      key: 'wifi',
      label: 'Wi-Fi',
      icon: <RadioTower size={13} aria-hidden="true" />,
      value: offline ? OFFLINE_VALUE : formatSigned(device.wifi_rssi, ' dBm'),
      sub: offline ? 'no link' : `${device.wifi_ssid ?? 'unknown SSID'} · ${device.ip_address ?? 'no IP'}`,
      tone: offline ? undefined : (device.wifi_rssi ?? -100) > -60 ? 'ok' : 'warn',
      barPercent: device?.wifi_rssi ? Math.max(4, Math.min(100, Math.round(((device.wifi_rssi + 100) / 70) * 100))) : 0,
    },
    {
      key: 'uptime',
      label: 'Uptime',
      icon: <Activity size={13} aria-hidden="true" />,
      value: offline ? OFFLINE_VALUE : formatUptime(device.uptime_ms),
      sub: offline ? 'device offline' : `firmware ${device.firmware_version ?? 'unknown'}`,
    },
  ];

  return (
    <div className="readout-grid" data-live={wsConnected}>
      {readouts.map((readout) => (
        <div className="readout" key={readout.key} data-active={readout.active ? 'true' : 'false'}>
          <span className="readout__label">
            <span className="readout__icon">{readout.icon}</span>
            {readout.label}
          </span>
          <span className="readout__value" data-tone={readout.tone}>
            {readout.value}
          </span>
          <span className="readout__sub">{readout.sub}</span>
          {readout.barPercent !== undefined && readout.barPercent > 0 ? (
            <span className="readout__bar" aria-hidden="true">
              <span className="readout__bar-fill" style={{ width: `${readout.barPercent}%` }} />
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
