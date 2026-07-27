import { ChevronRight, Plus, Trash2 } from 'lucide-react';

interface SelectionBarProps {
  label?: string;
  selectedName?: string;
  selectedDescription?: string;
  placeholder: string;
  onOpenPicker: () => void;
  onAdd?: () => void;
  onDelete?: () => void;
  canDelete?: boolean;
  addLabel?: string;
  disabled?: boolean;
  compact?: boolean;
}

export function SelectionBar({
  label,
  selectedName,
  selectedDescription,
  placeholder,
  onOpenPicker,
  onAdd,
  onDelete,
  canDelete = false,
  addLabel = 'Свой',
  disabled = false,
}: SelectionBarProps) {
  return (
    <div className="space-y-1.5">
      {label ? (
        <span className="text-[10px] font-medium text-[var(--corex-text-dim)]">{label}</span>
      ) : null}
      <div className="corex-picker-row">
        <button
          type="button"
          disabled={disabled}
          onClick={onOpenPicker}
          className="corex-picker-main disabled:opacity-50"
        >
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium text-[var(--corex-text)] truncate">
              {selectedName || placeholder}
            </div>
            {selectedDescription ? (
              <div className="text-[10px] text-[var(--corex-text-dim)] truncate mt-0.5">
                {selectedDescription}
              </div>
            ) : null}
          </div>
          <ChevronRight className="w-4 h-4 text-[var(--corex-text-dim)] flex-shrink-0" />
        </button>
        {onAdd ? (
          <button
            type="button"
            onClick={onAdd}
            disabled={disabled}
            title={addLabel}
            className="corex-picker-action disabled:opacity-50"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        ) : null}
        {canDelete && onDelete ? (
          <button
            type="button"
            onClick={onDelete}
            disabled={disabled}
            title="Удалить"
            className="corex-picker-action corex-picker-action--danger disabled:opacity-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        ) : null}
      </div>
    </div>
  );
}
