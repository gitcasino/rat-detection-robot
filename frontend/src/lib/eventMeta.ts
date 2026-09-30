import type { EventCategory, EventType } from '../types/telemetry';

/** Label + accent colour for every event type in the backend vocabulary. */

export interface EventDescriptor {
  label: string;
  category: EventCategory;
  /** CSS custom property that carries the accent colour. */
  tone: string;
  /** Short glyph shown in the log gutter; text label always accompanies it. */
  glyph: string;
}

export const EVENT_META: Record<EventType, EventDescriptor> = {
  DEVICE_ONLINE: { label: 'Device online', category: 'SYSTEM', tone: 'var(--ok)', glyph: '▲' },
  DEVICE_OFFLINE: { label: 'Device offline', category: 'SYSTEM', tone: 'var(--muted)', glyph: '▼' },
  VIBRATION_DETECTED: { label: 'Vibration', category: 'SENSORS', tone: 'var(--warn)', glyph: '≈' },
  VIBRATION_CLEARED: { label: 'Vibration cleared', category: 'SENSORS', tone: 'var(--muted)', glyph: '·' },
  IR_DETECTED: { label: 'Infrared', category: 'SENSORS', tone: 'var(--accent)', glyph: '◈' },
  IR_CLEARED: { label: 'IR cleared', category: 'SENSORS', tone: 'var(--muted)', glyph: '·' },
  DISTANCE_UPDATED: { label: 'Distance sample', category: 'SENSORS', tone: 'var(--muted)', glyph: '≋' },
  TARGET_ACTIVITY_DETECTED: { label: 'Activity detected', category: 'SENSORS', tone: 'var(--warn)', glyph: '◎' },
  TARGET_ACTIVITY_CLEARED: { label: 'Activity cleared', category: 'SENSORS', tone: 'var(--muted)', glyph: '○' },
  ROBOT_MOVING: { label: 'Robot moving', category: 'ROBOT', tone: 'var(--accent)', glyph: '→' },
  ROBOT_STOPPED: { label: 'Robot stopped', category: 'ROBOT', tone: 'var(--muted)', glyph: '■' },
  EMITTER_ACTIVATED: { label: 'Emitter activated', category: 'EMITTER', tone: 'var(--alert)', glyph: '◉' },
  EMITTER_DEACTIVATED: { label: 'Emitter deactivated', category: 'EMITTER', tone: 'var(--muted)', glyph: '◌' },
  OBSTACLE_DETECTED: { label: 'Obstacle detected', category: 'ROBOT', tone: 'var(--warn)', glyph: '▲' },
  OBSTACLE_CLEARED: { label: 'Obstacle cleared', category: 'ROBOT', tone: 'var(--ok)', glyph: '▽' },
  ERROR: { label: 'Error', category: 'ERROR', tone: 'var(--danger)', glyph: '✖' },
  HEARTBEAT: { label: 'Heartbeat', category: 'SYSTEM', tone: 'var(--muted)', glyph: '·' },
};

export const CATEGORY_ORDER: Array<EventCategory | 'ALL'> = [
  'ALL',
  'EMITTER',
  'SENSORS',
  'ROBOT',
  'SYSTEM',
  'ERROR',
];

export const CATEGORY_META: Record<EventCategory, { label: string; tone: string }> = {
  EMITTER: { label: 'Emitter', tone: 'var(--alert)' },
  SENSORS: { label: 'Sensors', tone: 'var(--warn)' },
  ROBOT: { label: 'Robot', tone: 'var(--accent)' },
  SYSTEM: { label: 'System', tone: 'var(--muted)' },
  ERROR: { label: 'Error', tone: 'var(--danger)' },
};

export const ROBOT_STATE_LABEL: Record<string, string> = {
  IDLE: 'Idle',
  TARGET_DETECTED: 'Target detected',
  APPROACHING: 'Approaching',
  OBSTACLE_AVOIDANCE: 'Obstacle avoidance',
  EMITTER_ACTIVE: 'Emitter active',
  MONITORING: 'Monitoring',
  ERROR: 'Error',
};
