import { describe, expect, it } from 'vitest';

import {
  formatBoolean,
  formatClockTime,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatJsonValue,
  formatSigned,
  formatUptime,
  relativeTime,
} from './format';

describe('formatDuration', () => {
  it('renders sub-minute, minute, hour and day ranges', () => {
    expect(formatDuration(0)).toBe('0s');
    expect(formatDuration(7.8)).toBe('7s');
    expect(formatDuration(59)).toBe('59s');
    expect(formatDuration(60)).toBe('1m 00s');
    expect(formatDuration(754)).toBe('12m 34s');
    expect(formatDuration(3600)).toBe('1h 00m');
    expect(formatDuration(9000)).toBe('2h 30m');
    expect(formatDuration(90000)).toBe('1d 01h');
  });

  it('shows a placeholder for missing or invalid values', () => {
    expect(formatDuration(null)).toBe('--');
    expect(formatDuration(undefined)).toBe('--');
    expect(formatDuration(-1)).toBe('--');
    expect(formatDuration(Number.NaN)).toBe('--');
  });
});

describe('formatUptime', () => {
  it('converts milliseconds to a human duration', () => {
    expect(formatUptime(0)).toBe('0s');
    expect(formatUptime(3_600_000)).toBe('1h 00m');
    expect(formatUptime(null)).toBe('--');
    expect(formatUptime(-1)).toBe('--');
  });
});

describe('clock helpers', () => {
  it('formats local wall-clock time with zero padding', () => {
    expect(formatClockTime('2026-03-01T09:05:07Z')).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(formatClockTime(null)).toBe('--:--:--');
    expect(formatClockTime('not-a-date')).toBe('--:--:--');
  });

  it('formats a full date and time, or reports the problem', () => {
    expect(formatDateTime('2026-03-01T09:05:07Z')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    expect(formatDateTime(null)).toBe('never');
    expect(formatDateTime('garbage')).toBe('invalid timestamp');
  });

  it('describes relative age', () => {
    const now = Date.parse('2026-03-01T10:00:00Z');
    expect(relativeTime('2026-03-01T09:59:58Z', now)).toBe('just now');
    expect(relativeTime('2026-03-01T09:58:00Z', now)).toBe('2m 00s ago');
    expect(relativeTime(null, now)).toBe('never');
    expect(relativeTime('nope', now)).toBe('invalid');
  });
});

describe('readout helpers', () => {
  it('formats distance with one decimal', () => {
    expect(formatDistance(18.24)).toBe('18.2 cm');
    expect(formatDistance(18.25)).toBe('18.3 cm');
    expect(formatDistance(0)).toBe('0.0 cm');
    expect(formatDistance(null)).toBe('--');
  });

  it('formats signed values such as RSSI', () => {
    expect(formatSigned(-58, ' dBm')).toBe('-58 dBm');
    expect(formatSigned(7)).toBe('+7');
    expect(formatSigned(0)).toBe('0');
    expect(formatSigned(null)).toBe('--');
  });

  it('renders tri-state booleans as text so colour is never the only signal', () => {
    expect(formatBoolean(true)).toBe('YES');
    expect(formatBoolean(false)).toBe('NO');
    expect(formatBoolean(null)).toBe('n/a');
  });

  it('serialises metadata values for display', () => {
    expect(formatJsonValue('text')).toBe('text');
    expect(formatJsonValue(12)).toBe('12');
    expect(formatJsonValue(true)).toBe('true');
    expect(formatJsonValue(null)).toBe('null');
    expect(formatJsonValue({ a: 1 })).toBe('{"a":1}');
  });
});
