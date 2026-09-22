import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { Sparkles, Play } from 'lucide-react';
import type { FilePatchHighlight } from '../types/editorPatch';

interface EditorTab {
  id: string;
  name: string;
  path: string;
  modified: boolean;
  language: string;
}

interface CodeEditorProps {
  tabs: EditorTab[];
  activeTabId: string;
  content: string;
  path: string;
  language: string;
  onContentChange: (path: string, content: string) => void;
  onSaveSuccess?: (path: string) => void;
  onRun?: () => void;
  canRun?: boolean;
  patchHighlights?: FilePatchHighlight[];
  revealRequest?: { path: string; line: number; token: number } | null;
}

const getApiHosts = () => {
  const hosts: string[] = [];
  if (window.electronAPI?.backendUrl) {
    hosts.push(window.electronAPI.backendUrl);
  }
  if (window.electronAPI?.backendPort) {
    hosts.push(`http://127.0.0.1:${window.electronAPI.backendPort}`);
  }
  hosts.push('http://127.0.0.1:8000', 'http://localhost:8000');
  return hosts;
};

export type CodeEditorHandle = {
  save: () => Promise<boolean>;
  revealLine: (line: number) => void;
};

export const CodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function CodeEditor({
  tabs,
  activeTabId,
  content,
  path,
  language,
  onContentChange,
  onSaveSuccess,
  onRun,
  canRun = false,
  patchHighlights = [],
  revealRequest = null,
}, ref) {
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationIdsRef = useRef<string[]>([]);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'dirty' | 'saving' | 'saved' | 'error'>('idle');
  const [saveMessage, setSaveMessage] = useState<string>('');
  const [editorModule, setEditorModule] = useState<any>(null);
  const [editorLoadError, setEditorLoadError] = useState<string>('');
  const [isEditorLoading, setIsEditorLoading] = useState(false);

  const activeTab = useMemo(() => tabs.find((tab) => tab.id === activeTabId), [tabs, activeTabId]);
  const safePath = activeTab?.path ?? path ?? '';
  const safeLanguage = activeTab?.language ?? language ?? 'plaintext';
  const safeContent = activeTab ? content ?? '' : '';

  useEffect(() => {
    if (!activeTab || editorModule || editorLoadError) {
      return;
    }

    setIsEditorLoading(true);
    import('@monaco-editor/react')
      .then((mod) => {
        setEditorModule(mod.default ?? mod);
      })
      .catch((error) => {
        console.error('Monaco Editor failed to load:', error);
        setEditorLoadError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => {
        setIsEditorLoading(false);
      });
  }, [activeTab, editorModule, editorLoadError]);

  useEffect(() => {
    const styleId = 'corex-diff-styles';
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        .corex-line-add { background: rgba(34, 197, 94, 0.3) !important; }
        .corex-line-modify { background: rgba(234, 179, 8, 0.3) !important; }
        .corex-line-delete { background: rgba(239, 68, 68, 0.25) !important; box-shadow: inset 3px 0 0 #ef4444; }
        .corex-glyph-add { background: #22c55e; }
        .corex-glyph-modify { background: #eab308; }
        .corex-glyph-delete { background: #ef4444; }
      `;
      document.head.appendChild(style);
    }
  }, []);

  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) {
      return;
    }

    if (!patchHighlights.length) {
      decorationIdsRef.current = editor.deltaDecorations(decorationIdsRef.current, []);
      return;
    }

    const lineCount = editor.getModel()?.getLineCount?.() ?? 1;
    const decorations = patchHighlights.map((item) => {
      const displayLine = Math.min(
        item.displayLine ?? item.line,
        Math.max(lineCount, 1),
      );
      const className =
        item.type === 'add'
          ? 'corex-line-add'
          : item.type === 'delete'
          ? 'corex-line-delete'
          : 'corex-line-modify';
      const glyphClassName =
        item.type === 'add'
          ? 'corex-glyph-add'
          : item.type === 'delete'
          ? 'corex-glyph-delete'
          : 'corex-glyph-modify';
      const hoverParts = [];
      if (item.old) {
        hoverParts.push(`Было: ${item.old}`);
      }
      if (item.new) {
        hoverParts.push(`Стало: ${item.new}`);
      }
      if (item.type === 'delete' && item.old) {
        hoverParts.push('Строка удалена');
      }

      return {
        range: new monaco.Range(displayLine, 1, displayLine, 1),
        options: {
          isWholeLine: true,
          className,
          linesDecorationsClassName: glyphClassName,
          hoverMessage: hoverParts.length
            ? { value: hoverParts.join('\n') }
            : undefined,
        },
      };
    });

    decorationIdsRef.current = editor.deltaDecorations(decorationIdsRef.current, decorations);
  }, [patchHighlights, safeContent, safePath]);

  useEffect(() => {
    if (activeTab?.modified) {
      setSaveStatus('dirty');
      setSaveMessage('Изменено');
    } else {
      setSaveStatus('idle');
      setSaveMessage('Сохранено');
    }
  }, [activeTab?.modified]);

  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.focus();
    }
  }, [safePath, activeTabId]);

  useEffect(() => {
    if (saveStatus === 'saved') {
      const timer = window.setTimeout(() => {
        setSaveStatus('idle');
        setSaveMessage('Сохранено');
      }, 1800);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [saveStatus]);

  const saveFile = useCallback(async (): Promise<boolean> => {
    if (!safePath) {
      setSaveStatus('error');
      setSaveMessage('Нет пути для сохранения');
      return false;
    }

    if (!activeTab?.modified) {
      setSaveStatus('idle');
      setSaveMessage('Нет изменений');
      return true;
    }

    const editorText = editorRef.current?.getValue?.() ?? safeContent;
    setSaveStatus('saving');
    setSaveMessage('Сохранение...');

    let lastError: unknown;
    for (const host of getApiHosts()) {
      try {
        const response = await fetch(`${host}/api/files/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: safePath, content: editorText, isDir: false }),
        });

        const result = await response.json();
        if (result.success) {
          setSaveStatus('saved');
          setSaveMessage('Файл сохранён');
          onSaveSuccess?.(safePath);
          return true;
        }

        setSaveStatus('error');
        setSaveMessage(result.error || 'Ошибка сохранения');
        return false;
      } catch (error) {
        lastError = error;
      }
    }

    setSaveStatus('error');
    setSaveMessage(`Ошибка сети: ${lastError}`);
    return false;
  }, [safePath, safeContent, activeTab?.modified, onSaveSuccess]);

  const saveFileRef = useRef(saveFile);
  saveFileRef.current = saveFile;

  const onRunRef = useRef(onRun);
  onRunRef.current = onRun;

  useImperativeHandle(ref, () => ({
    save: () => saveFileRef.current(),
    revealLine: (line: number) => {
      const editor = editorRef.current;
      if (!editor || !Number.isFinite(line)) {
        return;
      }
      const target = Math.max(1, Math.floor(line));
      editor.revealLineInCenter?.(target);
      editor.setPosition?.({ lineNumber: target, column: 1 });
      editor.focus?.();
    },
  }), []);

  const handleEditorMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    if (monaco?.KeyMod && monaco?.KeyCode) {
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KEY_S, () => {
        void saveFileRef.current();
      });
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KEY_F, () => {
        editor.getAction('actions.find').run();
      });
      editor.addCommand(monaco.KeyCode.F5, () => {
        onRunRef.current?.();
      });
    }

    editor.focus();
    if (revealRequest && revealRequest.path === safePath) {
      const target = Math.max(1, Math.floor(revealRequest.line));
      editor.revealLineInCenter?.(target);
      editor.setPosition?.({ lineNumber: target, column: 1 });
    }
  };

  useEffect(() => {
    if (!revealRequest || revealRequest.path !== safePath) {
      return;
    }
    const editor = editorRef.current;
    if (!editor) {
      return;
    }
    const target = Math.max(1, Math.floor(revealRequest.line));
    editor.revealLineInCenter?.(target);
    editor.setPosition?.({ lineNumber: target, column: 1 });
    editor.focus?.();
  }, [revealRequest, safePath, editorModule, safeContent]);

  const handleEditorChange = (value?: string) => {
    if (typeof value !== 'string') {
      return;
    }
    onContentChange(safePath, value);
    setSaveStatus('dirty');
    setSaveMessage('Изменено');
  };

  const statusBadgeClass =
    saveStatus === 'saving'
      ? 'bg-[#2563eb] text-white'
      : saveStatus === 'saved'
      ? 'bg-[#10b981] text-[#ecfdf5]'
      : saveStatus === 'dirty'
      ? 'bg-[#f59e0b] text-[#1f2937]'
      : saveStatus === 'error'
      ? 'bg-[#ef4444] text-white'
      : 'bg-[#111827] text-[#9ca3af]';

  if (!activeTab) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0b1220] border border-[#2c2f3a] rounded-xl p-6">
        <div className="text-center text-sm text-[#9ca3af]">Выберите файл, чтобы начать редактирование.</div>
      </div>
    );
  }

  if (editorLoadError) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0b1220] border border-[#2c2f3a] rounded-xl p-6">
        <div className="text-center text-sm text-[#fca5a5]">
          Ошибка загрузки редактора: {editorLoadError}
          <div className="mt-2 text-xs text-[#9ca3af]">Откройте DevTools для полного стека.</div>
        </div>
      </div>
    );
  }

  if (!editorModule || isEditorLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0b1220] border border-[#2c2f3a] rounded-xl p-6">
        <div className="text-center text-sm text-[#9ca3af]">Загрузка редактора Monaco...</div>
      </div>
    );
  }

  const Editor = editorModule;

  return (
    <div className="flex flex-col h-full bg-[#0b1220] border border-[#2c2f3a] rounded-xl shadow-[0_20px_60px_-30px_rgba(0,0,0,0.9)] overflow-hidden">
      <div className="flex justify-between items-center gap-2 bg-[#131824] border-b border-[#212733] px-4 py-2.5">
        <div className="flex items-center gap-2 text-[#c7d1e0] text-sm font-semibold">
          <Sparkles className="w-4 h-4 text-[#38bdf8]" />
          <span>{safePath ? safePath.split('/').pop() : 'Новый файл'}</span>
        </div>
        <div className="flex items-center gap-2">
          {onRun ? (
            <button
              type="button"
              onClick={onRun}
              disabled={!canRun}
              title={canRun ? 'Запустить файл (F5)' : 'Тип файла не поддерживается для запуска'}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-[#16a34a] text-white hover:bg-[#15803d] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              Запуск
            </button>
          ) : null}
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-[0.15em] ${statusBadgeClass}`}>
            {saveMessage}
          </span>
          <span className="text-xs uppercase tracking-[0.3em] text-[#6b7a93]">{safeLanguage}</span>
          {patchHighlights.length > 0 ? (
            <span className="text-[10px] text-[#9ca3af] flex items-center gap-2">
              <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[#22c55e]/60" />+</span>
              <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[#eab308]/60" />~</span>
              <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-[#ef4444]/60" />−</span>
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden">
        <Editor
          height="100%"
          defaultLanguage={safeLanguage}
          language={safeLanguage}
          value={safeContent}
          theme="vs-dark"
          onMount={handleEditorMount}
          onChange={handleEditorChange}
          options={{
            fontFamily: 'Fira Code, Consolas, monospace',
            fontSize: 14,
            lineNumbers: 'on',
            roundedSelection: false,
            scrollBeyondLastLine: false,
            smoothScrolling: true,
            automaticLayout: true,
            wordWrap: 'off',
            cursorBlinking: 'blink',
            contextmenu: true,
            tabSize: 2,
            insertSpaces: true,
            detectIndentation: true,
            renderLineHighlight: 'all',
            lineDecorationsWidth: 20,
            lineNumbersMinChars: 3,
            scrollbar: {
              vertical: 'visible',
              horizontal: 'auto',
              useShadows: false,
              verticalScrollbarSize: 10,
              horizontalScrollbarSize: 10,
            },
            minimap: {
              enabled: true,
              renderCharacters: false,
              maxColumn: 120,
            },
          }}
        />
      </div>
    </div>
  );
});
