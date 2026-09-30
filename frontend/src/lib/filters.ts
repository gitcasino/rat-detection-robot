/** Pure event-filter rules shared by the store and the log view. */

import { EVENT_META } from './eventMeta';
import type { EventFilters, TelemetryEvent } from '../types/telemetry';

export function matchesFilters(event: TelemetryEvent, filters: EventFilters): boolean {
  if (filters.category !== 'ALL' && event.category !== filters.category) {
    return false;
  }
  const needle = filters.search.trim().toLowerCase();
  if (needle.length === 0) {
    return true;
  }
  const haystack = [
    EVENT_META[event.event_type]?.label ?? event.event_type,
    event.device_id,
    event.message ?? '',
    event.detail ?? '',
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(needle);
}
