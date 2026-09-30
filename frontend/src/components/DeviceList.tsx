import { Cpu } from 'lucide-react';

import { relativeTime } from '../lib/format';
import type { DeviceTelemetryState } from '../types/telemetry';

export interface DeviceListProps {
  devices: DeviceTelemetryState[];
  selectedDeviceId: string | null;
  onSelect: (deviceId: string) => void;
}

export function DeviceList({ devices, selectedDeviceId, onSelect }: DeviceListProps) {
  return (
    <div className="device-list">
      {devices.map((device) => (
        <button
          key={device.device_id}
          type="button"
          className="device-row"
          aria-current={selectedDeviceId === device.device_id}
          onClick={() => onSelect(device.device_id)}
        >
          <span style={{ minWidth: 0 }}>
            <span className="device-row__id">{device.device_id}</span>
            <br />
            <span className="device-row__meta">
              {device.label ?? 'unlabelled'} · seen {relativeTime(device.last_seen_at)}
            </span>
          </span>
          <span className="device-row__flags">
            <span className="tag" data-tone={device.state === 'ONLINE' ? 'ok' : 'danger'}>
              <Cpu size={10} aria-hidden="true" />
              {device.state === 'ONLINE' ? 'online' : 'offline'}
            </span>
            {device.emitter_active ? (
              <span className="tag" data-tone="alert">
                emitter on
              </span>
            ) : null}
          </span>
        </button>
      ))}
    </div>
  );
}
