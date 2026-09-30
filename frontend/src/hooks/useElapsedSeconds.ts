import { useEffect, useState } from 'react';

/**
 * Elapsed seconds for a value the server keeps updating.
 *
 * The backend is authoritative, so the displayed figure is the server value; it
 * only re-renders once a second so a running activation timer stays visible.
 */
export function useElapsedSeconds(activatedAt: string | null, active: boolean): number {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!active) {
      return undefined;
    }
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);

  if (!active || !activatedAt) {
    return 0;
  }
  const start = new Date(activatedAt).getTime();
  if (Number.isNaN(start)) {
    return 0;
  }
  return Math.max(0, Math.round((nowMs - start) / 1000));
}
