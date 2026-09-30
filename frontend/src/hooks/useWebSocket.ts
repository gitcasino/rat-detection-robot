/**
 * WebSocket lifecycle with exponential backoff and an application-level keepalive.
 *
 * `offline` means the browser cannot reach the backend; `degraded` means the
 * backend answered but the stream dropped. The two are never conflated because
 * the operator needs to know whether the *robot* or the *link* is the problem.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { isServerFrame, type ServerFrame } from '../types/frames';

declare const __WS_URL__: string;

export const WS_URL: string = __WS_URL__;

export type SocketStatus = 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface UseWebSocketOptions {
  url?: string;
  enabled?: boolean;
  onFrame: (frame: ServerFrame) => void;
  onStatusChange?: (status: SocketStatus) => void;
  /** Application keepalive interval; the backend answers with a `pong` frame. */
  keepaliveMs?: number;
  maxBackoffMs?: number;
}

export interface WebSocketState {
  status: SocketStatus;
  lastFrameAt: number | null;
  lastError: string | null;
}

const BASE_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 15000;

export function useWebSocket({
  url = WS_URL,
  enabled = true,
  onFrame,
  onStatusChange,
  keepaliveMs = 20000,
  maxBackoffMs = MAX_BACKOFF_MS,
}: UseWebSocketOptions): WebSocketState {
  const [status, setStatus] = useState<SocketStatus>('connecting');
  const [lastFrameAt, setLastFrameAt] = useState<number | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(BASE_BACKOFF_MS);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const keepaliveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Callbacks are read through refs so a re-rendering parent never tears down
  // the socket.
  const onFrameRef = useRef(onFrame);
  const onStatusChangeRef = useRef(onStatusChange);

  useEffect(() => {
    onFrameRef.current = onFrame;
  }, [onFrame]);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  }, [onStatusChange]);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (keepaliveTimerRef.current !== null) {
      clearInterval(keepaliveTimerRef.current);
      keepaliveTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled || typeof WebSocket === 'undefined') {
      return undefined;
    }

    let disposed = false;

    const applyStatus = (next: SocketStatus): void => {
      setStatus(next);
      onStatusChangeRef.current?.(next);
    };

    const open = (): void => {
      if (disposed) {
        return;
      }
      applyStatus(attemptRef.current === 0 ? 'connecting' : 'reconnecting');

      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch (error) {
        setLastError(error instanceof Error ? error.message : 'WebSocket construction failed');
        scheduleReconnect();
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        if (disposed) {
          return;
        }
        attemptRef.current = 0;
        backoffRef.current = BASE_BACKOFF_MS;
        setLastError(null);
        applyStatus('open');
        keepaliveTimerRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          }
        }, keepaliveMs);
      };

      socket.onmessage = (message: MessageEvent<string>) => {
        if (disposed) {
          return;
        }
        let payload: unknown;
        try {
          payload = JSON.parse(message.data);
        } catch {
          return; // Ignore malformed frames rather than tearing down the stream.
        }
        if (!isServerFrame(payload)) {
          return;
        }
        setLastFrameAt(Date.now());
        onFrameRef.current(payload);
      };

      socket.onerror = () => {
        setLastError('WebSocket transport error');
      };

      socket.onclose = (event: CloseEvent) => {
        if (disposed) {
          return;
        }
        if (keepaliveTimerRef.current !== null) {
          clearInterval(keepaliveTimerRef.current);
          keepaliveTimerRef.current = null;
        }
        socketRef.current = null;
        setLastError(
          event.reason && event.reason.length > 0
            ? event.reason
            : `WebSocket closed (code ${event.code})`,
        );
        scheduleReconnect();
      };
    };

    const scheduleReconnect = (): void => {
      if (disposed) {
        return;
      }
      const delay = Math.min(backoffRef.current, maxBackoffMs);
      // Jitter keeps several tabs from reconnecting in lockstep.
      const jitter = Math.round(delay * 0.2 * Math.random());
      backoffRef.current = Math.min(backoffRef.current * 2, maxBackoffMs);
      attemptRef.current += 1;
      applyStatus('reconnecting');
      reconnectTimerRef.current = setTimeout(open, delay + jitter);
    };

    open();

    return () => {
      disposed = true;
      clearTimers();
      const socket = socketRef.current;
      socketRef.current = null;
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      }
      setStatus('closed');
    };
  }, [enabled, url, keepaliveMs, maxBackoffMs, clearTimers]);

  return { status, lastFrameAt, lastError };
}
