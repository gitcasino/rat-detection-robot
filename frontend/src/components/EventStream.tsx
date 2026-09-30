import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDownUp, Download, Radar, Search, X } from 'lucide-react';
import { useId, useMemo } from 'react';

import { useAutoScroll } from '../hooks/useAutoScroll';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { CATEGORY_META, CATEGORY_ORDER, EVENT_META } from '../lib/eventMeta';
import { formatClockTime } from '../lib/format';
import type { EventCategory, EventFilters, TelemetryEvent } from '../types/telemetry';
import { EmptyState } from './EmptyState';

export interface EventStreamProps {
  events: TelemetryEvent[];
  filters: EventFilters;
  historyTotal: number;
  selectedEventId: number | null;
  pristine: boolean;
  linkState: 'live' | 'degraded' | 'offline';
  onFilterChange: (filters: Partial<EventFilters>) => void;
  onClearFilters: () => void;
  onSelect: (eventId: number) => void;
  onRefresh: () => void;
  onExport: () => void;
}

export function EventStream({
  events,
  filters,
  historyTotal,
  selectedEventId,
  pristine,
  linkState,
  onFilterChange,
  onClearFilters,
  onSelect,
  onRefresh,
  onExport,
}: EventStreamProps) {
  const reducedMotion = usePrefersReducedMotion();
  const searchId = useId();
  const { containerRef, unseenCount, onScroll, scrollToBottom } = useAutoScroll(events);
  const counts = useMemo(() => {
    const tally = new Map<EventCategory | 'ALL', number>();
    for (const category of CATEGORY_ORDER) {
      tally.set(category, 0);
    }
    for (const event of events) {
      tally.set('ALL', (tally.get('ALL') ?? 0) + 1);
      tally.set(event.category, (tally.get(event.category) ?? 0) + 1);
    }
    return tally;
  }, [events]);

  return (
    <div className="log">
      <div className="log__filters">
        {CATEGORY_ORDER.map((category) => {
          const selected = filters.category === category;
          const label = category === 'ALL' ? 'All' : (CATEGORY_META[category as EventCategory].label ?? category);
          return (
            <button
              key={category}
              type="button"
              className="chip"
              aria-pressed={selected}
              onClick={() => onFilterChange({ category })}
            >
              {label}
              <span className="chip__count">{counts.get(category) ?? 0}</span>
            </button>
          );
        })}

        <label className="search" htmlFor={searchId}>
          <Search size={12} aria-hidden="true" />
          <span className="visually-hidden">Filter events by text</span>
          <input
            id={searchId}
            type="search"
            value={filters.search}
            placeholder="filter text"
            onChange={(event) => onFilterChange({ search: event.target.value })}
          />
          {filters.search.length > 0 ? (
            <button type="button" className="action action--ghost" onClick={() => onFilterChange({ search: '' })}>
              <X size={11} aria-hidden="true" />
              <span className="visually-hidden">Clear text filter</span>
            </button>
          ) : null}
        </label>

        <button
          type="button"
          className="chip"
          aria-pressed={filters.order === 'asc'}
          title="Toggle chronological order"
          onClick={() => onFilterChange({ order: filters.order === 'asc' ? 'desc' : 'asc' })}
        >
          <ArrowDownUp size={11} aria-hidden="true" />
          {filters.order === 'asc' ? 'Oldest first' : 'Newest first'}
        </button>
      </div>

      <div className="log__scroll" ref={containerRef} onScroll={onScroll} role="log" aria-live="polite" aria-label="Event log">
        {events.length === 0 ? (
          <EmptyState
            icon={<Radar size={26} />}
            title={pristine ? 'No telemetry yet' : 'No matching events'}
            detail={
              pristine
                ? linkState === 'live'
                  ? 'The console is connected and waiting. Events appear here as soon as the ESP32 reports them; nothing is ever fabricated.'
                  : 'The backend is not reachable, so the log is empty. It fills automatically once the robot reports.'
                : 'The current filter hides every event in the loaded window. Clear the filter to see the full log.'
            }
            action={
              pristine ? (
                <button type="button" className="action" onClick={onRefresh}>
                  Reload history
                </button>
              ) : (
                <button type="button" className="action" onClick={onClearFilters}>
                  Clear filters
                </button>
              )
            }
          />
        ) : (
          <ul className="log__list">
            <AnimatePresence initial={false}>
              {events.map((event) => {
                const meta = EVENT_META[event.event_type];
                return (
                  <motion.li
                    key={event.id}
                    layout={!reducedMotion}
                    initial={reducedMotion ? false : { opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={reducedMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
                    transition={{ duration: reducedMotion ? 0 : 0.18 }}
                  >
                    <button
                      type="button"
                      className="log__row"
                      data-category={event.category}
                      aria-current={selectedEventId === event.id}
                      onClick={() => onSelect(event.id)}
                    >
                      <span className="log__time">{formatClockTime(event.occurred_at)}</span>
                      <span className="log__glyph" style={{ color: meta?.tone }} aria-hidden="true">
                        {meta?.glyph ?? '·'}
                      </span>
                      <span className="log__type" style={{ color: meta?.tone }}>
                        {meta?.label ?? event.event_type}
                      </span>
                      <span className="log__message">{event.message ?? event.event_type.toLowerCase()}</span>
                    </button>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
        )}

        {unseenCount > 0 ? (
          <button type="button" className="log__new" onClick={scrollToBottom}>
            {unseenCount} new {unseenCount === 1 ? 'event' : 'events'}
          </button>
        ) : null}
      </div>

      <div className="log__footer">
        <span>
          {events.length} shown · {historyTotal} stored
        </span>
        <span style={{ display: 'inline-flex', gap: 10 }}>
          <button type="button" className="action action--ghost" onClick={onRefresh}>
            Reload
          </button>
          <button type="button" className="action action--ghost" onClick={onExport} disabled={events.length === 0}>
            <Download size={11} aria-hidden="true" />
            JSON
          </button>
        </span>
      </div>
    </div>
  );
}
