import { Copy, Check, User, Bot } from 'lucide-react';
import { useState } from 'react';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export function ChatMessage({ role, content, timestamp }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex gap-4 p-4 ${role === 'assistant' ? 'bg-muted/30' : ''}`}>
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
        role === 'user'
          ? 'bg-gradient-to-br from-blue-500 to-blue-600'
          : 'bg-gradient-to-br from-purple-500 to-purple-600'
      }`}>
        {role === 'user' ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-semibold text-foreground">
            {role === 'user' ? 'Вы' : 'CoreX AI'}
          </span>
          {timestamp && (
            <span className="text-xs text-muted-foreground">{timestamp}</span>
          )}
        </div>

        <div className="text-foreground whitespace-pre-wrap break-words">
          {content}
        </div>

        {role === 'assistant' && (
          <div className="flex gap-2 mt-3">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3" />
                  <span>Скопировано</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Копировать</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
