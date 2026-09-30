/**
 * Typed REST client for the FastAPI backend.
 *
 * Every helper fails soft: the dashboard shows a connection state instead of
 * throwing, so a stopped backend renders a clear banner rather than a blank page.
 */

import type {
  DeviceTelemetryState,
  EmitterSession,
  EventCategory,
  EventPage,
  EventType,
  HealthResponse,
  StatsResponse,
  StatusResponse,
  TelemetryEvent,
} from '../types/telemetry';

declare const __API_BASE_URL__: string;

export const API_BASE_URL: string = __API_BASE_URL__;

const REQUEST_TIMEOUT_MS = 8000;

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export type QueryValue = string | number | boolean | undefined | null | Array<string | number>;

/** Arrays become repeated query parameters, which is what the FastAPI routes expect. */
export function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        search.append(key, String(item));
      }
      continue;
    }
    if (value === undefined || value === null || value === '') {
      continue;
    }
    search.append(key, String(value));
  }
  const query = search.toString();
  return query.length > 0 ? `?${query}` : '';
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const onAbort = (): void => controller.abort();
  signal?.addEventListener('abort', onAbort);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new ApiError(`GET ${path} failed with ${response.status}`, response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(error instanceof Error ? error.message : 'Network request failed', 0);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

export interface EventQuery {
  deviceId?: string;
  types?: EventType[];
  categories?: EventCategory[];
  search?: string;
  since?: string;
  until?: string;
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export function getStatus(signal?: AbortSignal): Promise<StatusResponse> {
  return request<StatusResponse>('/api/status', signal);
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health', signal);
}

export function getDevices(signal?: AbortSignal): Promise<DeviceTelemetryState[]> {
  return request<DeviceTelemetryState[]>('/api/devices', signal);
}

export function getDevice(deviceId: string, signal?: AbortSignal): Promise<DeviceTelemetryState> {
  return request<DeviceTelemetryState>(`/api/devices/${encodeURIComponent(deviceId)}`, signal);
}

export function getEvent(eventId: number, signal?: AbortSignal): Promise<TelemetryEvent> {
  return request<TelemetryEvent>(`/api/events/${eventId}`, signal);
}

export function getEvents(query: EventQuery = {}, signal?: AbortSignal): Promise<EventPage> {
  return request<EventPage>(
    `/api/events${buildQuery({
      device_id: query.deviceId,
      type: query.types,
      category: query.categories,
      search: query.search,
      since: query.since,
      until: query.until,
      order: query.order ?? 'desc',
      limit: query.limit ?? 100,
      offset: query.offset ?? 0,
    })}`,
    signal,
  );
}

export function getEmitterSessions(
  deviceId: string,
  limit = 25,
  signal?: AbortSignal,
): Promise<EmitterSession[]> {
  return request<EmitterSession[]>(
    `/api/devices/${encodeURIComponent(deviceId)}/emitter-sessions${buildQuery({ limit })}`,
    signal,
  );
}

export function getStats(windowHours = 24, signal?: AbortSignal): Promise<StatsResponse> {
  return request<StatsResponse>(`/api/stats${buildQuery({ window_hours: windowHours })}`, signal);
}
