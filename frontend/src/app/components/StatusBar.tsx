import { GitBranch, AlertCircle, CheckCircle, Wifi, WifiOff, Cpu } from 'lucide-react';

interface StatusBarProps {
  isOnline: boolean;
  appVersion?: string;
  updateStatus?: string;
}

export function StatusBar({ isOnline, appVersion = '', updateStatus = '' }: StatusBarProps) {
  return (
    <div className="corex-statusbar relative">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <GitBranch className="w-3 h-3 text-[var(--corex-brand)]" />
          <span>main</span>
        </div>
        <div className="flex items-center gap-1.5 text-emerald-400/90">
          <CheckCircle className="w-3 h-3" />
          <span>Нет ошибок</span>
        </div>
        <div className="flex items-center gap-1.5 opacity-70">
          <AlertCircle className="w-3 h-3" />
          <span>0 предупреждений</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          {isOnline ? (
            <>
              <Wifi className="w-3 h-3 text-[var(--corex-spark)]" />
              <span className="text-[var(--corex-spark)]">Онлайн API</span>
            </>
          ) : (
            <>
              <Cpu className="w-3 h-3 text-[var(--corex-brand)]" />
              <span className="text-[var(--corex-brand)]">Ollama · локально</span>
            </>
          )}
        </div>
        {isOnline ? <WifiOff className="hidden" /> : null}
        <span className="opacity-60">UTF-8</span>
        {appVersion ? <span className="opacity-60 font-mono">v{appVersion}</span> : null}
        {updateStatus ? <span className="text-[var(--corex-spark)]">{updateStatus}</span> : null}
      </div>
    </div>
  );
}
