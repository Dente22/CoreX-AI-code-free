import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Circle, X, List, XCircle } from 'lucide-react';

export interface EditorTabItem {
  id: string;
  name: string;
  path: string;
  modified: boolean;
  language: string;
}

interface EditorTabsBarProps {
  tabs: EditorTabItem[];
  activeTabId: string;
  onSelectTab: (id: string) => void;
  onCloseTab: (id: string) => void;
  onCloseOthers?: (keepId: string) => void;
  onCloseAll?: () => void;
}

const EXT_COLORS: Record<string, string> = {
  py: '#519aba',
  js: '#f0db4f',
  ts: '#3178c6',
  tsx: '#3178c6',
  jsx: '#61dafb',
  html: '#e44d26',
  css: '#42a5f5',
  json: '#cbcb41',
  md: '#519aba',
  mmd: '#9a5eff',
  web: '#22d3ee',
};

function tabExt(name: string, language?: string) {
  if (language === 'browser') return 'web';
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : '';
}

export function EditorTabsBar({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onCloseOthers,
  onCloseAll,
}: EditorTabsBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);

  const modifiedCount = useMemo(() => tabs.filter((t) => t.modified).length, [tabs]);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  }, [activeTabId]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [menuOpen]);

  if (tabs.length === 0) return null;

  return (
    <div className="corex-editor-tabs flex items-stretch min-h-9 bg-[var(--corex-surface)] border-b border-[var(--corex-border)]">
      <div ref={scrollRef} className="corex-editor-tabs-scroll flex-1 flex items-stretch overflow-x-auto">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          const ext = tabExt(tab.name, tab.language);
          const extColor = EXT_COLORS[ext] ?? 'var(--corex-text-dim)';

          return (
            <button
              key={tab.id}
              ref={isActive ? activeRef : undefined}
              type="button"
              title={tab.path}
              onClick={() => onSelectTab(tab.id)}
              className={`corex-editor-tab group shrink-0 ${isActive ? 'corex-editor-tab--active' : ''}`}
            >
              <span
                className="text-[9px] font-bold uppercase tracking-wide px-1 py-0.5 rounded"
                style={{ color: extColor, background: `${extColor}22` }}
              >
                {ext || '·'}
              </span>
              <span className="max-w-[7rem] truncate text-xs font-medium">{tab.name}</span>
              {tab.modified && (
                <Circle className="w-1.5 h-1.5 fill-[var(--corex-spark)] text-[var(--corex-spark)] shrink-0" />
              )}
              <span
                role="button"
                tabIndex={0}
                aria-label={`Закрыть ${tab.name}`}
                className="corex-editor-tab-close"
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseTab(tab.id);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.stopPropagation();
                    e.preventDefault();
                    onCloseTab(tab.id);
                  }
                }}
              >
                <X className="w-3 h-3" />
              </span>
            </button>
          );
        })}
      </div>

      <div className="relative flex items-center shrink-0 border-l border-[var(--corex-border)] px-1">
        <button
          type="button"
          className="corex-editor-tabs-menu-btn"
          title="Все вкладки"
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((v) => !v);
          }}
        >
          <List className="w-3.5 h-3.5" />
          <span className="text-[10px] font-semibold tabular-nums">{tabs.length}</span>
          <ChevronDown className={`w-3 h-3 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
        </button>

        {menuOpen && (
          <div
            className="corex-editor-tabs-dropdown"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-[var(--corex-text-dim)] border-b border-[var(--corex-border)]">
              Открытые файлы
              {modifiedCount > 0 && (
                <span className="ml-2 text-[var(--corex-spark)]">· {modifiedCount} не сохранено</span>
              )}
            </div>
            <div className="max-h-56 overflow-y-auto py-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={`corex-editor-tabs-dropdown-item ${tab.id === activeTabId ? 'corex-editor-tabs-dropdown-item--active' : ''}`}
                  onClick={() => {
                    onSelectTab(tab.id);
                    setMenuOpen(false);
                  }}
                >
                  <span className="truncate flex-1 text-left">{tab.name}</span>
                  {tab.modified && <Circle className="w-1.5 h-1.5 fill-[var(--corex-spark)] shrink-0" />}
                  <span
                    role="button"
                    tabIndex={0}
                    className="p-0.5 rounded hover:bg-[var(--corex-surface-hover)] text-[var(--corex-text-dim)]"
                    onClick={(e) => {
                      e.stopPropagation();
                      onCloseTab(tab.id);
                    }}
                  >
                    <X className="w-3 h-3" />
                  </span>
                </button>
              ))}
            </div>
            {(onCloseOthers || onCloseAll) && tabs.length > 1 && (
              <div className="border-t border-[var(--corex-border)] p-1 flex gap-1">
                {onCloseOthers && (
                  <button
                    type="button"
                    className="corex-editor-tabs-action"
                    onClick={() => {
                      onCloseOthers(activeTabId);
                      setMenuOpen(false);
                    }}
                  >
                    Закрыть остальные
                  </button>
                )}
                {onCloseAll && (
                  <button
                    type="button"
                    className="corex-editor-tabs-action text-red-400"
                    onClick={() => {
                      onCloseAll();
                      setMenuOpen(false);
                    }}
                  >
                    <XCircle className="w-3 h-3" />
                    Все
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
