import { ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { useState } from 'react';
import { fileWordRu, type FileStatusEntry } from '../utils/chatFileStatus';

interface ChatFileGroupProps {
  files: FileStatusEntry[];
  onOpenFile?: (path: string, name: string) => void;
}

export function ChatFileGroup({ files, onOpenFile }: ChatFileGroupProps) {
  const [expanded, setExpanded] = useState(false);
  const count = files.length;
  if (count === 0) {
    return null;
  }

  const preview = files[0]?.name ?? '';
  const canToggle = count > 1;
  const showList = canToggle && expanded;

  return (
    <div className="corex-chat-file-group">
      <button
        type="button"
        className="corex-chat-file-group-toggle"
        onClick={() => {
          if (canToggle) {
            setExpanded((value) => !value);
          } else if (files[0]) {
            onOpenFile?.(files[0].path || files[0].name, files[0].name);
          }
        }}
        aria-expanded={canToggle ? expanded : undefined}
        title={canToggle ? undefined : `Открыть ${preview}`}
      >
        {canToggle ? (
          expanded ? (
            <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-[var(--corex-text-dim)]" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 text-[var(--corex-text-dim)]" />
          )
        ) : (
          <FileText className="w-3.5 h-3.5 flex-shrink-0 text-[var(--corex-spark)]" />
        )}
        <span className="corex-chat-file-group-title">
          {count} {fileWordRu(count)}
        </span>
        {!showList && preview ? (
          <span className="corex-chat-file-group-preview">
            {preview}
            {count > 1 ? ` +${count - 1}` : ''}
          </span>
        ) : null}
        {count === 1 ? (
          <span className="corex-chat-file-group-action">{files[0].action}</span>
        ) : null}
      </button>

      {showList ? (
        <ul className="corex-chat-file-group-list">
          {files.map((file) => (
            <li key={file.id}>
              <button
                type="button"
                className="corex-chat-file-group-item"
                onClick={() => onOpenFile?.(file.path || file.name, file.name)}
                title={file.content}
              >
                <FileText className="w-3 h-3 flex-shrink-0 text-[var(--corex-spark)]" />
                <span className="truncate">{file.name}</span>
                <span className="corex-chat-file-group-action ml-auto">{file.action}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
