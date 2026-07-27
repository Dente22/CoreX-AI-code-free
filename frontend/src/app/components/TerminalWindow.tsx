import { Terminal as TerminalIcon, X, Plus, History, Play } from 'lucide-react';
import { useState } from 'react';

interface TerminalWindowProps {
  id: string;
  title: string;
  onClose: (id: string) => void;
}

export function TerminalWindow({ id, title, onClose }: TerminalWindowProps) {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([
    '$ npm run dev',
    '> vite',
    '',
    'VITE v6.3.5  ready in 372 ms',
    '',
    '✓ Local:   http://127.0.0.1:5176/',
    '✓ press h + enter to show help',
    '',
    'Ready for input...',
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      setHistory([...history, `$ ${input}`]);
      setInput('');
    }
  };

  return (
    <div className="absolute bottom-0 right-0 w-96 h-80 bg-[#181818] border border-[#2b2b2b] rounded-t flex flex-col shadow-lg">
      <div className="h-9 flex items-center justify-between px-3 border-b border-[#2b2b2b] bg-[#252526]">
        <div className="flex items-center gap-2">
          <TerminalIcon className="w-4 h-4 text-[#cccccc]" />
          <span className="text-[#cccccc] text-sm font-semibold">{title}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            title="Новый терминал"
            className="w-6 h-6 flex items-center justify-center text-[#cccccc] hover:text-white hover:bg-[#2a2d2e] transition-colors rounded text-xs"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            type="button"
            title="История"
            className="w-6 h-6 flex items-center justify-center text-[#cccccc] hover:text-white hover:bg-[#2a2d2e] transition-colors rounded text-xs"
          >
            <History className="w-4 h-4" />
          </button>
          <button
            type="button"
            title="Запуск кода"
            className="w-6 h-6 flex items-center justify-center text-[#cccccc] hover:text-white hover:bg-[#2a2d2e] transition-colors rounded text-xs"
          >
            <Play className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => onClose(id)}
            title="Закрыть"
            className="w-6 h-6 flex items-center justify-center text-[#cccccc] hover:text-white hover:bg-[#2a2d2e] transition-colors rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 font-mono text-sm bg-[#1e1e1e]">
        {history.map((line, i) => (
          <div 
            key={`${i}-${line}`} 
            className={line.startsWith('$') ? 'text-[#4ec9b0]' : 'text-[#cccccc]'}
          >
            {line}
          </div>
        ))}
        <form onSubmit={handleSubmit} className="flex items-center text-[#4ec9b0] mt-1">
          <span>$ </span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder=""
            className="flex-1 bg-transparent outline-none ml-1 text-[#cccccc]"
            autoFocus
          />
        </form>
      </div>
    </div>
  );
}
