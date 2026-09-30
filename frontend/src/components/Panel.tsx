import type { ReactNode } from 'react';

export interface PanelProps {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  variant?: 'default' | 'emitter' | 'log';
  flush?: boolean;
  className?: string;
}

const variantClass: Record<NonNullable<PanelProps['variant']>, string> = {
  default: '',
  emitter: 'panel__header--emitter',
  log: 'panel__header--log',
};

export function Panel({ title, aside, children, variant = 'default', flush = false, className }: PanelProps) {
  const classes = ['panel', className].filter(Boolean).join(' ');
  return (
    <section className={classes}>
      <header className={`panel__header ${variantClass[variant]}`.trim()}>
        <span className="panel__title">{title}</span>
        <span className="panel__spacer" />
        {aside ? <span className="panel__aside">{aside}</span> : null}
      </header>
      <div className={flush ? 'panel__body panel__body--flush' : 'panel__body'}>{children}</div>
    </section>
  );
}
