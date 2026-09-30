import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { getEmitterSessions } from '../lib/api';
import { EVENT_META, ROBOT_STATE_LABEL } from '../lib/eventMeta';
import {
  formatBoolean,
  formatClockTime,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatJsonValue,
  relativeTime,
} from '../lib/format';
import type { EmitterSession, TelemetryEvent } from '../types/telemetry';

export interface EventDetailProps {
  event: TelemetryEvent | null;
  onClose: () => void;
}

function Field({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'warn' | 'danger' }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd data-tone={tone}>{value}</dd>
    </div>
  );
}

export function EventDetail({ event, onClose }: EventDetailProps) {
  const [sessions, setSessions] = useState<EmitterSession[]>([]);
  const [sessionState, setSessionState] = useState<'idle' | 'loading' | 'ready' | 'failed'>('idle');

  useEffect(() => {
    if (!event || event.category !== 'EMITTER' || event.device_id.length === 0) {
      setSessions([]);
      setSessionState('idle');
      return undefined;
    }
    const controller = new AbortController();
    setSessionState('loading');
    void getEmitterSessions(event.device_id, 8, controller.signal)
      .then((rows) => {
        setSessions(rows);
        setSessionState('ready');
      })
      .catch(() => {
        setSessionState('failed');
      });
    return () => controller.abort();
  }, [event]);

  useEffect(() => {
    if (!event) {
      return undefined;
    }
    const onKeyDown = (keyboardEvent: KeyboardEvent): void => {
      if (keyboardEvent.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [event, onClose]);

  const metadata = useMemo(
    () => Object.entries(event?.metadata ?? {}).sort(([left], [right]) => left.localeCompare(right)),
    [event],
  );

  return (
    <AnimatePresence>
      {event ? (
        <motion.div
          className="drawer-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label={`Event detail: ${EVENT_META[event.event_type]?.label ?? event.event_type}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
        >
          <motion.aside
            className="drawer"
            initial={{ x: 40 }}
            animate={{ x: 0 }}
            exit={{ x: 40 }}
            transition={{ duration: 0.18 }}
            onClick={(clickEvent) => clickEvent.stopPropagation()}
          >
            <header className="drawer__header">
              <span className="drawer__title">
                {EVENT_META[event.event_type]?.label ?? event.event_type}
              </span>
              <span className="panel__spacer" />
              <button type="button" className="action action--ghost" onClick={onClose} aria-label="Close event detail">
                <X size={13} aria-hidden="true" />
              </button>
            </header>

            <div className="drawer__body">
              <dl className="field-grid">
                <Field label="Event id" value={String(event.id)} />
                <Field label="Type" value={event.event_type} />
                <Field label="Category" value={event.category} />
                <Field label="Source" value={event.source === 'SERVER' ? 'server reconciled' : 'device reported'} />
                <Field label="Device" value={event.device_id} />
                <Field label="Occurred" value={formatDateTime(event.occurred_at)} />
                <Field
                  label="Received"
                  value={`${formatDateTime(event.received_at)} (${relativeTime(event.received_at)})`}
                />
                <Field
                  label="Device clock"
                  value={event.device_timestamp_rejected ? 'rejected: implausible' : 'accepted'}
                  tone={event.device_timestamp_rejected ? 'warn' : 'ok'}
                />
                <Field label="Distance" value={formatDistance(event.distance_cm)} />
                <Field label="Vibration" value={formatBoolean(event.vibration)} />
                <Field label="Infrared" value={formatBoolean(event.ir_detected)} />
                <Field label="Emitter" value={formatBoolean(event.emitter_active)} />
                <Field label="Robot state" value={event.robot_state ? (ROBOT_STATE_LABEL[event.robot_state] ?? event.robot_state) : 'n/a'} />
                <Field
                  label="Emitter duration"
                  value={event.emitter_duration_seconds != null ? formatDuration(event.emitter_duration_seconds) : 'n/a'}
                />
                <Field label="Message" value={event.message ?? 'n/a'} />
                {event.detail ? <Field label="Detail" value={event.detail} /> : null}
              </dl>

              {metadata.length > 0 ? (
                <>
                  <h3 className="section-title">Metadata</h3>
                  <dl className="field-grid">
                    {metadata.map(([key, value]) => (
                      <Field key={key} label={key} value={formatJsonValue(value)} />
                    ))}
                  </dl>
                </>
              ) : null}

              {event.category === 'EMITTER' ? (
                <>
                  <h3 className="section-title">Recent sessions for {event.device_id}</h3>
                  {sessionState === 'loading' ? (
                    <p className="empty__detail">Loading activation windows…</p>
                  ) : sessionState === 'failed' ? (
                    <p className="empty__detail">Activation windows could not be loaded.</p>
                  ) : sessions.length === 0 ? (
                    <p className="empty__detail">No activation windows recorded yet.</p>
                  ) : (
                    <div className="session-list">
                      {sessions.map((session) => (
                        <div className="session" key={session.id}>
                          <span className="session__time">{formatClockTime(session.activated_at)}</span>
                          <span className="session__time">
                            {session.deactivated_at ? formatClockTime(session.deactivated_at) : 'open'}
                          </span>
                          <span className="session__meta">
                            {session.deactivated_at
                              ? `duration ${formatDuration(session.duration_seconds)}`
                              : 'activation still open'}
                          </span>
                          <span className="session__meta">id {session.id}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
