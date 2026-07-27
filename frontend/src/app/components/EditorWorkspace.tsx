import { forwardRef, useState } from 'react';
import { Code2, GitBranch } from 'lucide-react';
import { CodeEditor, type CodeEditorHandle } from './CodeEditor';
import { VisioPanel } from './VisioPanel';
import { EditorTabsBar } from './EditorTabsBar';
import type { FilePatchHighlight } from '../types/editorPatch';

interface EditorTab {
  id: string;
  name: string;
  path: string;
  modified: boolean;
  language: string;
}

type WorkspaceTab = 'edit' | 'visio';

interface EditorWorkspaceProps {
  tabs: EditorTab[];
  activeTabId: string;
  onSelectTab: (id: string) => void;
  onCloseTab: (id: string) => void;
  onCloseOtherTabs?: (keepId: string) => void;
  onCloseAllTabs?: () => void;
  content: string;
  path: string;
  language: string;
  onContentChange: (path: string, content: string) => void;
  onSaveSuccess?: (path: string) => void;
  onRun?: () => void;
  canRun?: boolean;
  projectRoot: string;
  onOpenDiagramFile?: (path: string) => void;
  hasOpenTabs: boolean;
  patchHighlights?: FilePatchHighlight[];
}

export const EditorWorkspace = forwardRef<CodeEditorHandle, EditorWorkspaceProps>(
  function EditorWorkspace(
    {
      tabs,
      activeTabId,
      onSelectTab,
      onCloseTab,
      onCloseOtherTabs,
      onCloseAllTabs,
      content,
      path,
      language,
      onContentChange,
      onSaveSuccess,
      onRun,
      canRun,
      projectRoot,
      onOpenDiagramFile,
      hasOpenTabs,
      patchHighlights = [],
    },
    ref,
  ) {
    const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('edit');

    return (
      <div className="flex flex-col h-full min-h-0 gap-0">
        <div className="flex items-center gap-1 px-2 py-1.5 bg-[var(--corex-surface)] border border-[var(--corex-border)] rounded-t-xl">
          <button
            type="button"
            onClick={() => setWorkspaceTab('edit')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
              workspaceTab === 'edit'
                ? 'bg-[rgba(0,210,255,0.12)] text-[var(--corex-spark)] border border-[var(--corex-spark)]/30'
                : 'text-[var(--corex-text-muted)] hover:text-[var(--corex-text)]'
            }`}
          >
            <Code2 className="w-4 h-4" />
            Редактировать
          </button>
          <button
            type="button"
            onClick={() => setWorkspaceTab('visio')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
              workspaceTab === 'visio'
                ? 'bg-[rgba(154,94,255,0.12)] text-[var(--corex-brand)] border border-[var(--corex-brand)]/30'
                : 'text-[var(--corex-text-muted)] hover:text-[var(--corex-text)]'
            }`}
          >
            <GitBranch className="w-4 h-4" />
            Visio
          </button>
        </div>

        {workspaceTab === 'edit' && hasOpenTabs && (
          <EditorTabsBar
            tabs={tabs}
            activeTabId={activeTabId}
            onSelectTab={onSelectTab}
            onCloseTab={onCloseTab}
            onCloseOthers={onCloseOtherTabs}
            onCloseAll={onCloseAllTabs}
          />
        )}

        <div className="flex-1 min-h-0">
          {workspaceTab === 'visio' ? (
            <VisioPanel projectRoot={projectRoot} onOpenDiagramFile={onOpenDiagramFile} />
          ) : hasOpenTabs ? (
            <CodeEditor
              ref={ref}
              tabs={tabs}
              activeTabId={activeTabId}
              content={content}
              path={path}
              language={language}
              onContentChange={onContentChange}
              onSaveSuccess={onSaveSuccess}
              onRun={onRun}
              canRun={canRun}
              patchHighlights={patchHighlights}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center rounded-b-xl border border-[var(--corex-border)] bg-[var(--corex-panel)] p-8 text-center">
              <div className="w-14 h-14 rounded-2xl bg-[rgba(0,210,255,0.1)] border border-[var(--corex-spark)]/20 flex items-center justify-center mb-4">
                <Code2 className="w-7 h-7 text-[var(--corex-spark)]" />
              </div>
              <h2 className="text-xl font-semibold text-[var(--corex-text)] mb-2">Откройте файл из проводника</h2>
              <p className="text-[var(--corex-text-muted)] text-sm mb-5 max-w-sm">или переключитесь на Visio, чтобы увидеть схему работы проекта</p>
              <button
                type="button"
                onClick={() => setWorkspaceTab('visio')}
                className="corex-btn-primary px-5 py-2.5 text-sm"
              >
                Открыть Visio
              </button>
            </div>
          )}
        </div>
      </div>
    );
  },
);
