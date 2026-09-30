/** Display formatting. Every helper is pure so it can be unit tested. */

const pad = (value: number, size = 2): string => value.toString().padStart(size, '0');

export function formatClockTime(iso: string | null | undefined): string {
  if (!iso) {
    return '--:--:--';
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return '--:--:--';
  }
  return `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) {
    return 'never';
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return 'invalid timestamp';
  }
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ${formatClockTime(iso)}`;
}

/** Compact human duration: 3s, 12m 04s, 2h 07m, 4d 01h. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) {
    return '--';
  }
  const total = Math.floor(seconds);
  if (total < 60) {
    return `${total}s`;
  }
  if (total < 3600) {
    return `${Math.floor(total / 60)}m ${pad(total % 60)}s`;
  }
  if (total < 86400) {
    return `${Math.floor(total / 3600)}h ${pad(Math.floor((total % 3600) / 60))}m`;
  }
  return `${Math.floor(total / 86400)}d ${pad(Math.floor((total % 86400) / 3600))}h`;
}

export function formatUptime(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms) || ms < 0) {
    return '--';
  }
  return formatDuration(ms / 1000);
}

export function formatDistance(distanceCm: number | null | undefined): string {
  if (distanceCm === null || distanceCm === undefined) {
    return '--';
  }
  return `${distanceCm.toFixed(1)} cm`;
}

export function formatSigned(value: number | null | undefined, unit = ''): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '--';
  }
  return `${value > 0 ? '+' : ''}${value}${unit}`;
}

export function formatBoolean(value: boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return 'n/a';
  }
  return value ? 'YES' : 'NO';
}

export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) {
    return 'never';
  }
  const parsed = new Date(iso).getTime();
  if (Number.isNaN(parsed)) {
    return 'invalid';
  }
  const deltaSeconds = Math.max(0, Math.round((now - parsed) / 1000));
  if (deltaSeconds < 5) {
    return 'just now';
  }
  return `${formatDuration(deltaSeconds)} ago`;
}

export function formatJsonValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'null';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}
