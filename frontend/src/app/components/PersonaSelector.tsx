import { useMemo, useState } from 'react';
import { Plus, Search, Sparkles, Trash2 } from 'lucide-react';
import type { Persona } from '../utils/personas';

interface PersonaSelectorProps {
  personas: Persona[];
  selectedId: string;
  onChange: (personaId: string) => void;
  onAdd: () => void;
  onDelete?: (personaId: string) => void;
  disabled?: boolean;
}

function groupPersonas(personas: Persona[]): [string, Persona[]][] {
  const library = personas.filter((p) => p.source !== 'project');
  const mine = personas.filter((p) => p.source === 'project');

  const map = new Map<string, Persona[]>();
  for (const persona of library) {
    const key = persona.category_ru || 'Прочее';
    const list = map.get(key) || [];
    list.push(persona);
    map.set(key, list);
  }

  const groups = [...map.entries()].sort(([a], [b]) => a.localeCompare(b, 'ru'));
  if (mine.length > 0) {
    groups.push(['Мои скилы', mine]);
  }
  return groups;
}

export function PersonaSelector({
  personas,
  selectedId,
  onChange,
  onAdd,
  onDelete,
  disabled = false,
}: PersonaSelectorProps) {
  const [query, setQuery] = useState('');
  const selected = personas.find((p) => p.id === selectedId);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return personas;
    }
    return personas.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.category_ru || '').toLowerCase().includes(q) ||
        (p.description || '').toLowerCase().includes(q),
    );
  }, [personas, query]);

  const groups = useMemo(() => groupPersonas(filtered), [filtered]);
  const canDelete = selected?.source === 'project' && onDelete;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 px-1">
        <Sparkles className="w-4 h-4 text-purple-400 flex-shrink-0" />
        <div className="flex-1 relative min-w-0">
          <Search className="w-3.5 h-3.5 text-[#6b7280] absolute left-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск скила..."
            disabled={disabled}
            className="w-full bg-[#0f1720] text-[#e5e9f0] text-xs border border-[#212733] rounded-md pl-7 pr-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#2563eb] disabled:opacity-50"
          />
        </div>
      </div>

      <div className="flex items-center gap-2 px-1">
        <select
          value={selectedId}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          aria-label="Выбор скила"
          title={selected?.description || 'Выберите скил из библиотеки CoreX или свои'}
          className="flex-1 min-w-0 bg-[#0f1720] text-[#e5e9f0] text-xs border border-[#212733] rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-[#2563eb] disabled:opacity-50"
        >
          <option value="">
            {personas.length === 0 ? '— Нет скилов —' : '— Выберите скил —'}
          </option>
          {groups.map(([label, items]) => (
            <optgroup key={label} label={label}>
              {items.map((persona) => (
                <option key={persona.id} value={persona.id}>
                  {persona.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <button
          type="button"
          onClick={onAdd}
          disabled={disabled}
          title="Добавить свой скил"
          className="flex items-center gap-1 px-2 py-1.5 text-xs text-[#e5e9f0] bg-[#0f1720] border border-[#212733] rounded-md hover:bg-[#1a2332] disabled:opacity-50 whitespace-nowrap"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Свой</span>
        </button>
        {canDelete ? (
          <button
            type="button"
            onClick={() => onDelete(selectedId)}
            disabled={disabled}
            title="Удалить свой скил"
            className="p-1.5 text-red-400/80 hover:text-red-300 border border-[#212733] rounded-md disabled:opacity-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        ) : null}
      </div>

      <p className="text-[10px] text-[#6b7280] px-1">
        {personas.filter((p) => p.source !== 'project').length} скилов CoreX
        {personas.filter((p) => p.source === 'project').length > 0
          ? ` · ${personas.filter((p) => p.source === 'project').length} своих`
          : ''}
        {query ? ` · найдено: ${filtered.length}` : ''}
      </p>
    </div>
  );
}
