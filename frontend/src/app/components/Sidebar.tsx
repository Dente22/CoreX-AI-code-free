import { MessageSquare, Plus, Settings, ChevronLeft, ChevronRight, Trash2, Search } from 'lucide-react';
import { useState } from 'react';
import { CoreXLogo } from './CoreXLogo';

interface Chat {
  id: string;
  title: string;
  timestamp: string;
}

interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({ isCollapsed, onToggleCollapse }: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [chats] = useState<Chat[]>([
    { id: '1', title: 'Создать React компонент', timestamp: '2 мин назад' },
    { id: '2', title: 'Исправить баг в API', timestamp: '1 час назад' },
    { id: '3', title: 'Оптимизация производительности', timestamp: 'Вчера' },
    { id: '4', title: 'Написать тесты для utils', timestamp: '3 дня назад' },
    { id: '5', title: 'Рефакторинг компонентов', timestamp: 'Неделя назад' },
  ]);

  const filteredChats = chats.filter(chat =>
    chat.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (isCollapsed) {
    return (
      <div className="flex flex-col w-12 bg-sidebar border-r border-sidebar-border h-full">
        <button
          onClick={onToggleCollapse}
          className="p-3 hover:bg-sidebar-accent transition-colors"
        >
          <ChevronRight className="w-5 h-5 text-sidebar-foreground" />
        </button>
        <button className="p-3 hover:bg-sidebar-accent transition-colors">
          <Plus className="w-5 h-5 text-sidebar-foreground" />
        </button>
        <div className="flex-1" />
        <button className="p-3 hover:bg-sidebar-accent transition-colors">
          <Settings className="w-5 h-5 text-sidebar-foreground" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-64 bg-sidebar border-r border-sidebar-border h-full">
      <div className="flex items-center justify-between p-3 border-b border-sidebar-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg overflow-hidden ring-1 ring-[var(--corex-brand)]/40 flex items-center justify-center bg-[var(--corex-surface)]">
            <CoreXLogo className="w-6 h-6" />
          </div>
          <span className="font-semibold text-sidebar-foreground">CoreX</span>
        </div>
        <button
          onClick={onToggleCollapse}
          className="p-1 hover:bg-sidebar-accent rounded transition-colors"
        >
          <ChevronLeft className="w-4 h-4 text-sidebar-foreground" />
        </button>
      </div>

      <div className="p-2">
        <button className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-sidebar-primary text-sidebar-primary-foreground hover:opacity-90 transition-opacity">
          <Plus className="w-4 h-4" />
          <span>Новый чат</span>
        </button>
      </div>

      <div className="px-2 pb-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Поиск чатов..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-sidebar-accent text-sidebar-foreground placeholder:text-muted-foreground border-0 focus:outline-none focus:ring-2 focus:ring-sidebar-ring"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {filteredChats.map((chat) => (
          <button
            key={chat.id}
            className="w-full flex items-start gap-2 px-3 py-2 rounded-lg hover:bg-sidebar-accent transition-colors text-left group"
          >
            <MessageSquare className="w-4 h-4 mt-0.5 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-sidebar-foreground truncate">{chat.title}</div>
              <div className="text-xs text-muted-foreground">{chat.timestamp}</div>
            </div>
            <button className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-sidebar-border rounded">
              <Trash2 className="w-3 h-3 text-muted-foreground" />
            </button>
          </button>
        ))}
      </div>

      <div className="border-t border-sidebar-border p-2">
        <button className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-sidebar-accent transition-colors text-sidebar-foreground">
          <Settings className="w-4 h-4" />
          <span>Настройки</span>
        </button>
      </div>
    </div>
  );
}
