import { describe, expect, it } from 'vitest';

import { API_BASE_URL, buildQuery, getEmitterSessions, getEvents, getStats, getStatus } from '../lib/api';

const jsonResponse = (body: unknown, status = 200): Response =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as Response;

describe('buildQuery', () => {
  it('omits empty values and encodes the rest', () => {
    expect(buildQuery({ limit: 100, offset: 0, search: '', device_id: undefined, since: null })).toBe(
      '?limit=100&offset=0',
    );
  });

  it('repeats array parameters as FastAPI expects', () => {
    expect(buildQuery({ type: ['EMITTER_ACTIVATED', 'ERROR'], category: ['EMITTER'] })).toBe(
      '?type=EMITTER_ACTIVATED&type=ERROR&category=EMITTER',
    );
  });

  it('returns an empty string when nothing survives', () => {
    expect(buildQuery({ a: undefined, b: null, c: '' })).toBe('');
  });
});

describe('api client', () => {
  it('targets the injected backend base URL', () => {
    expect(API_BASE_URL).toBe('http://localhost:8000');
  });

  it('requests status, events, stats and sessions with the documented query parameters', async () => {
    const calls: string[] = [];
    const fetchMock = async (input: string): Promise<Response> => {
      calls.push(input);
      return jsonResponse({ items: [], total: 0 });
    };
    vi.stubGlobal('fetch', fetchMock);

    await getStatus();
    await getEvents({ deviceId: 'ESP32-01', categories: ['EMITTER'], order: 'asc', limit: 25, offset: 50 });
    await getStats(48);
    await getEmitterSessions('ESP32-01', 5);

    expect(calls[0]).toBe('http://localhost:8000/api/status');
    expect(calls[1]).toBe(
      'http://localhost:8000/api/events?device_id=ESP32-01&category=EMITTER&order=asc&limit=25&offset=50',
    );
    expect(calls[2]).toBe('http://localhost:8000/api/stats?window_hours=48');
    expect(calls[3]).toBe('http://localhost:8000/api/devices/ESP32-01/emitter-sessions?limit=5');
  });

  it('escapes device identifiers in the path', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', async (input: string) => {
      calls.push(input);
      return jsonResponse([]);
    });

    await getEmitterSessions('esp 32/01');
    expect(calls[0]).toBe('http://localhost:8000/api/devices/esp%2032%2F01/emitter-sessions?limit=25');
  });

  it('raises ApiError with the status code for non-2xx responses', async () => {
    vi.stubGlobal('fetch', async () => jsonResponse({ detail: 'nope' }, 503));
    await expect(getStatus()).rejects.toMatchObject({ name: 'ApiError', status: 503 });
  });

  it('raises ApiError when the request cannot be made at all', async () => {
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('Failed to fetch');
    });
    await expect(getStatus()).rejects.toMatchObject({ name: 'ApiError', status: 0 });
  });
});
