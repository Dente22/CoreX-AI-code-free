import React from 'react';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: any) {
    // Log to console so developer can inspect in renderer devtools
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-full p-6">
          <div className="bg-[#1b1b1b] border border-[#2b2b2b] rounded p-6 max-w-lg text-center">
            <h3 className="text-white font-semibold mb-2">Ошибка рендерера</h3>
            <div className="text-sm text-[#b6b6b6] mb-4">Произошла ошибка при рендеринге компонента. Откройте DevTools для деталей.</div>
            <details className="text-xs text-[#9ca3af] text-left max-h-40 overflow-auto">
              <summary>Показать ошибку</summary>
              <pre className="whitespace-pre-wrap break-words mt-2">{String(this.state.error)}</pre>
            </details>
          </div>
        </div>
      );
    }

    return this.props.children as JSX.Element;
  }
}

export default ErrorBoundary;
