import type { ReactNode } from 'react';

interface AIControlSectionProps {
  title: string;
  hint?: string;
  children: ReactNode;
}

export function AIControlSection({ title, hint, children }: AIControlSectionProps) {
  return (
    <div className="corex-control-section">
      <div className="corex-control-section-header">
        <span className="corex-control-section-title">{title}</span>
        {hint ? <span className="corex-control-section-hint">{hint}</span> : null}
      </div>
      <div className="corex-control-section-body">{children}</div>
    </div>
  );
}
