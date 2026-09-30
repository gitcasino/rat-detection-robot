/**
 * Minimal controllable WebSocket double.
 *
 * jsdom ships a real WebSocket that would try to reach ws://localhost:8000 and
 * fail asynchronously, which makes stream-driven tests racy. This fake lets a
 * test open the socket and push server frames by hand.
 */

import type { DeviceTelemetryState } from '../types/telemetry';

export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readyState: number = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  static reset(): void {
    FakeWebSocket.instances = [];
  }

  static get last(): FakeWebSocket | null {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1] ?? null;
  }

  static install(): void {
    FakeWebSocket.reset();
    vi.stubGlobal('WebSocket', FakeWebSocket);
  }

  send(payload: string): void {
    this.sent.push(payload);
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code: 1000, reason: 'client closing' } as CloseEvent);
  }

  /** Completes the handshake, optionally delivering a frame immediately. */
  openWith(frame?: unknown): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
    if (frame !== undefined) {
      this.emit(frame);
    }
  }

  emit(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  /** Simulates a transport failure after a successful connection. */
  drop(code = 1006, reason = ''): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onerror?.();
    this.onclose?.({ code, reason } as CloseEvent);
  }
}

export function snapshotFrame(devices: DeviceTelemetryState[]): unknown {
  return {
    type: 'snapshot',
    server_time: '2026-03-01T10:00:00Z',
    backend: { websocket: 'connected', websocket_clients: 1, backend: 'online' },
    devices,
    events: [],
    device_filter: null,
  };
}
