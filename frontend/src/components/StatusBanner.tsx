import { formatClockTime } from '../lib/format';
import type { LinkState } from '../types/telemetry';

export interface StatusBannerProps {
  linkState: LinkState;
  error: string | null;
  devicesOffline: number;
  deviceOfflineSince: string | null;
}

interface BannerSpec {
  key: string;
  tone: 'ok' | 'warn' | 'danger';
  title: string;
  detail: string;
  glyph?: string;
}

const BANNER_GLYPH: Record<BannerSpec['tone'], string> = {
  danger: '✖',
  warn: '▲',
  ok: '●',
};

/**
 * A dead backend is reported on its own; otherwise the stream and device states
 * are reported together, because an operator needs both facts at once: a robot
 * can be offline while the console link is fine, and vice versa.
 */
function resolveBanners({
  linkState,
  error,
  devicesOffline,
  deviceOfflineSince,
}: StatusBannerProps): BannerSpec[] {
  if (linkState === 'offline') {
    return [
      {
        key: 'backend',
        tone: 'danger',
        title: 'Backend offline',
        detail:
          error && error.length > 0
            ? `No telemetry can be received: ${error}. Values below are the last known state.`
            : 'No telemetry can be received. Values below are the last known state.',
      },
    ];
  }

  const banners: BannerSpec[] = [];

  if (linkState === 'degraded') {
    banners.push({
      key: 'stream',
      tone: 'warn',
      title: 'Live stream interrupted',
      detail: `The backend is reachable but the WebSocket stream is down. The console falls back to polling every 20 seconds; reconnect is automatic.`,
    });
  }

  if (devicesOffline > 0) {
    banners.push({
      key: 'device',
      tone: 'warn',
      title: devicesOffline === 1 ? 'ESP32 offline' : `${devicesOffline} devices offline`,
      detail:
        deviceOfflineSince && deviceOfflineSince.length > 0
          ? `The robot stopped reporting at ${formatClockTime(deviceOfflineSince)}. Emitter state is shown as OFFLINE until it returns.`
          : 'The robot stopped reporting. Emitter state is shown as OFFLINE until it returns.',
    });
  }

  return banners;
}

export function StatusBanner(props: StatusBannerProps) {
  const banners = resolveBanners(props);
  if (banners.length === 0) {
    return null;
  }
  return (
    <>
      {banners.map((banner) => (
        <div className="banner" data-tone={banner.tone} role="alert" key={banner.key}>
          <span className="banner__icon" aria-hidden="true">
            {banner.glyph ?? BANNER_GLYPH[banner.tone]}
          </span>
          <div className="banner__body">
            <span className="banner__title">{banner.title}</span>
            <span className="banner__detail">{banner.detail}</span>
          </div>
        </div>
      ))}
    </>
  );
}
