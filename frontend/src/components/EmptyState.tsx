import type { ReactNode } from 'react';

export interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  detail: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, detail, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <span className="empty__icon" aria-hidden="true">
        {icon}
      </span>
      <p className="empty__title">{title}</p>
      <p className="empty__detail">{detail}</p>
      {action}
    </div>
  );
}
