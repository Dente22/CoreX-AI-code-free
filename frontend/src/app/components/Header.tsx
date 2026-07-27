import { Cpu, Zap, Wifi, WifiOff } from 'lucide-react';

interface HeaderProps {
  isLocalMode: boolean;
}

export function Header({ isLocalMode }: HeaderProps) {
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card">
      <div className="flex items-center gap-4">
        <h2 className="text-foreground">CoreX AI Assistant</h2>
        <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-muted">
          <Cpu className="w-3 h-3 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Локальная модель</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-green-500/10">
          <Zap className="w-3 h-3 text-green-500" />
          <span className="text-xs text-green-500">Активен</span>
        </div>

        <div className="flex items-center gap-2 px-2 py-1 rounded-md bg-muted">
          {isLocalMode ? (
            <>
              <WifiOff className="w-3 h-3 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Оффлайн режим</span>
            </>
          ) : (
            <>
              <Wifi className="w-3 h-3 text-blue-500" />
              <span className="text-xs text-blue-500">Онлайн</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
