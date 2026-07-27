import { useEffect, useId, useState } from 'react';
import mermaid from 'mermaid';

let mermaidReady = false;

function ensureMermaid() {
  if (mermaidReady) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
    flowchart: { curve: 'basis', htmlLabels: true },
  });
  mermaidReady = true;
}

interface MermaidDiagramProps {
  source: string;
  className?: string;
}

export function MermaidDiagram({ source, className = '' }: MermaidDiagramProps) {
  const reactId = useId().replace(/:/g, '');
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!source.trim()) {
      setSvg('');
      setError('Нет данных для диаграммы');
      return;
    }

    let cancelled = false;
    ensureMermaid();
    const renderId = `mmd-${reactId}-${Date.now()}`;

    mermaid
      .render(renderId, source)
      .then(({ svg: rendered }) => {
        if (!cancelled) {
          setSvg(rendered);
          setError('');
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSvg('');
          setError(err instanceof Error ? err.message : 'Ошибка рендера Mermaid');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [source, reactId]);

  if (error) {
    return (
      <div className={`rounded-lg border border-red-900/50 bg-red-950/30 p-4 text-sm text-red-300 ${className}`}>
        {error}
        <pre className="mt-3 max-h-40 overflow-auto text-xs text-red-200/80 whitespace-pre-wrap">{source}</pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className={`flex items-center justify-center text-sm text-[#9ca3af] ${className}`}>
        Рисуем схему…
      </div>
    );
  }

  return (
    <div
      className={`overflow-auto flex items-center justify-center p-4 ${className}`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
