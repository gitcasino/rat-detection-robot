import { useEffect, useState } from 'react';

import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';

export interface BootSequenceProps {
  onDone?: () => void;
}

const LINES: Array<{ text: string; tone?: 'dim' | 'accent' }> = [
  { text: 'R.A.T. TELEMETRY CONSOLE / v1.0.0' },
  { text: 'POST ........................................ ok', tone: 'dim' },
  { text: 'loading event vocabulary .................. ok', tone: 'dim' },
  { text: 'handshake backend /api/status .............', tone: 'accent' },
  { text: 'awaiting ESP32 telemetry stream .........' },
];

const LINE_INTERVAL_MS = 130;
const HOLD_MS = 420;

/** Short boot log. Purely decorative: skipped entirely for reduced motion. */
export function BootSequence({ onDone = () => undefined }: BootSequenceProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [visible, setVisible] = useState(reducedMotion);
  const [count, setCount] = useState(reducedMotion ? LINES.length : 0);

  useEffect(() => {
    if (reducedMotion) {
      setVisible(false);
      onDone();
      return undefined;
    }
    const timer = setInterval(() => {
      setCount((current) => {
        if (current >= LINES.length) {
          return current;
        }
        return current + 1;
      });
    }, LINE_INTERVAL_MS);
    const done = setTimeout(() => {
      setVisible(false);
      onDone();
    }, LINES.length * LINE_INTERVAL_MS + HOLD_MS);
    return () => {
      clearInterval(timer);
      clearTimeout(done);
    };
  }, [reducedMotion, onDone]);

  if (!visible) {
    return null;
  }

  return (
    <div className="boot" role="status" aria-label="Starting telemetry console">
      <div className="boot__inner">
        {LINES.slice(0, count).map((line, index) => (
          <span className="boot__line" data-tone={line.tone} key={line.text}>
            {line.text}
            {index === count - 1 ? <span className="boot__cursor" /> : null}
          </span>
        ))}
      </div>
    </div>
  );
}
