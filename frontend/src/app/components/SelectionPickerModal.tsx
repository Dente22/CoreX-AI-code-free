import { useMemo, useState } from 'react';
import { Search, X, Check } from 'lucide-react';

export interface PickerItem {
  id: string;
  name: string;
  description?: string;
  category_ru?: string;
  meta?: string;
  source?: string;
}

export interface PickerFilter {
  id: string;
  label: string;
}

interface SelectionPickerModalProps {
  open: boolean;
  title: string;
  items: PickerItem[];
  selectedId: string;
  filters: PickerFilter[];
  onClose: () => void;
  onSelect: (id: string) => void;
  matchFilter?: (item: PickerItem, filterId: string) => boolean;
}

function defaultMatchFilter(item: PickerItem, filterId: string): boolean {
  if (filterId === 'all') return true;
  if (filterId === 'mine') return item.source === 'project';
  if (filterId === 'corex') return item.source === 'library';
  return item.category_ru === filterId;
}

export function SelectionPickerModal({
  open,
  title,
  items,
  selectedId,
  filters,
  onClose,
  onSelect,
  matchFilter = defaultMatchFilter,
}: SelectionPickerModalProps) {
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      if (!matchFilter(item, activeFilter)) return false;
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        (item.description || '').toLowerCase().includes(q) ||
        (item.category_ru || '').toLowerCase().includes(q) ||
        (item.meta || '').toLowerCase().includes(q)
      );
    });
  }, [items, query, activeFilter, matchFilter]);

  if (!open) return null;

  const handleSelect = (id: string) => {
    onSelect(id);
    onClose();
    setQuery('');
    setActiveFilter('all');
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4">
      <div
        className="w-full max-w-lg max-h-[85vh] flex flex-col bg-[#1a1d24] border border-[#2b2b2b] rounded-xl shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="picker-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2b2b2b] flex-shrink-0">
          <h2 id="picker-title" className="text-sm font-semibold text-[#e5e9f0]">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-[#858585] hover:text-white rounded"
            aria-label="Закрыть"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-4 pt-3 pb-2 flex-shrink-0 space-y-3">
          <div className="relative">
            <Search className="w-4 h-4 text-[#6b7280] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Поиск..."
              autoFocus
              className="w-full bg-[#0f1720] text-[#e5e9f0] text-sm border border-[#212733] rounded-lg pl-9 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-[#2563eb]"
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {filters.map((filter) => (
              <button
                key={filter.id}
                type="button"
                onClick={() => setActiveFilter(filter.id)}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                  activeFilter === filter.id
                    ? 'bg-[#2563eb] border-[#2563eb] text-white'
                    : 'bg-[#0f1720] border-[#212733] text-[#9ca3af] hover:text-white'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
          {filtered.length === 0 ? (
            <p className="text-sm text-[#6b7280] text-center py-8">Ничего не найдено</p>
          ) : (
            <ul className="space-y-1.5">
              {filtered.map((item) => {
                const isSelected = item.id === selectedId;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => handleSelect(item.id)}
                      className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors ${
                        isSelected
                          ? 'bg-[#1e3a5f] border-[#2563eb]'
                          : 'bg-[#0f1720] border-[#212733] hover:border-[#3b4a63] hover:bg-[#131a28]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-medium text-[#e5e9f0]">{item.name}</span>
                            {item.category_ru ? (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#212733] text-[#9ca3af]">
                                {item.category_ru}
                              </span>
                            ) : null}
                            {item.meta ? (
                              <span className="text-[10px] text-[#6b7280]">{item.meta}</span>
                            ) : null}
                          </div>
                          {item.description ? (
                            <p className="text-xs text-[#6b7280] mt-1 line-clamp-2">{item.description}</p>
                          ) : null}
                        </div>
                        {isSelected ? <Check className="w-4 h-4 text-[#60a5fa] flex-shrink-0 mt-0.5" /> : null}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <p className="px-4 py-2 text-[10px] text-[#6b7280] border-t border-[#2b2b2b] flex-shrink-0">
          {filtered.length} из {items.length}
        </p>
      </div>
    </div>
  );
}
