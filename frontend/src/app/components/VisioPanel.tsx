import { useCallback, useEffect, useMemo, useState } from 'react';
import { GitBranch, RefreshCw, FileCode2 } from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import { useViewSettings } from '../contexts/ViewSettingsContext';
import { MermaidDiagram } from './MermaidDiagram';
import {
  TERMINAL_VISIO_VIEWS,
  buildAiModeDiagram,
  fetchVisio,
  getDefaultProjectViewId,
  getDiagramSource,
  isTerminalView,
  type VisioPayload,
  type VisioViewId,
} from '../utils/visio';

interface VisioPanelProps {
  projectRoot: string;
  onOpenDiagramFile?: (path: string) => void;
}

export function VisioPanel({ projectRoot, onOpenDiagramFile }: VisioPanelProps) {
  const { terminalVisio } = useViewSettings();
  const {
    workMode,
    personas,
    agents,
    pipelines,
    selectedPersonaId,
    selectedAgentId,
    selectedPipelineId,
    isThinking,
  } = useChat();

  const [viewId, setViewId] = useState<VisioViewId>('structure');
  const [payload, setPayload] = useState<VisioPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadVisio = useCallback(async () => {
    if (!projectRoot) {
      setPayload(null);
      return;
    }
    setLoading(true);
    setError('');
    const data = await fetchVisio();
    setPayload(data);
    if (!data) {
      setError('Не удалось загрузить диаграммы проекта');
    } else {
      setViewId((current) => {
        if (isTerminalView(current) && !terminalVisio) {
          return getDefaultProjectViewId(data);
        }
        const exists =
          isTerminalView(current) ||
          data.diagrams.some((diagram) => diagram.id === current);
        return exists ? current : getDefaultProjectViewId(data);
      });
    }
    setLoading(false);
  }, [projectRoot, terminalVisio]);

  useEffect(() => {
    void loadVisio();
  }, [loadVisio]);

  useEffect(() => {
    if (!terminalVisio && isTerminalView(viewId)) {
      setViewId(getDefaultProjectViewId(payload));
    }
  }, [terminalVisio, viewId, payload]);

  const aiDiagram = useMemo(
    () =>
      buildAiModeDiagram(
        workMode,
        personas,
        agents,
        pipelines,
        selectedPersonaId,
        selectedAgentId,
        selectedPipelineId,
      ),
    [
      workMode,
      personas,
      agents,
      pipelines,
      selectedPersonaId,
      selectedAgentId,
      selectedPipelineId,
    ],
  );

  const diagramSource = getDiagramSource(viewId, payload, aiDiagram);
  const activeProjectDiagram = payload?.diagrams.find((d) => d.id === viewId);

  const originHint = isTerminalView(viewId)
    ? TERMINAL_VISIO_VIEWS.find((v) => v.id === viewId)?.hint ?? 'Терминальный Visio'
    : activeProjectDiagram
      ? activeProjectDiagram.origin === 'file' && activeProjectDiagram.path
        ? `Файл: ${activeProjectDiagram.path}`
        : `Схема проекта «${payload?.project_name ?? ''}»`
      : payload
        ? `Проект: ${payload.project_name}`
        : 'Откройте папку проекта';

  const editablePath =
    activeProjectDiagram?.origin === 'file' && activeProjectDiagram.path
      ? activeProjectDiagram.path
      : payload?.paths.workflow;

  return (
    <div className="flex flex-col h-full bg-[#0b1220] border border-[#2c2f3a] rounded-xl overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#131824] border-b border-[#212733] px-4 py-3">
        <div className="flex items-center gap-2 text-[#c7d1e0] text-sm font-semibold">
          <GitBranch className="w-4 h-4 text-[#a78bfa]" />
          <span>Visio — {payload?.project_name ?? 'проект'}</span>
          {isThinking ? (
            <span className="text-xs font-normal text-[#38bdf8] animate-pulse">AI работает…</span>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => void loadVisio()}
          disabled={loading}
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border border-[#334155] text-[#94a3b8] hover:text-white hover:border-[#475569] disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5 px-4 py-2 border-b border-[#212733] bg-[#0f141f]">
        {payload?.diagrams.map((diagram) => (
          <button
            key={diagram.id}
            type="button"
            onClick={() => setViewId(diagram.id)}
            title={diagram.path || diagram.label}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              viewId === diagram.id
                ? 'bg-[#0f766e] text-white'
                : 'bg-[#1e293b] text-[#94a3b8] hover:text-white'
            }`}
          >
            {diagram.label}
          </button>
        ))}

        {terminalVisio ? (
          <>
            <span className="self-center text-[#475569] text-xs px-1">|</span>
            {TERMINAL_VISIO_VIEWS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setViewId(item.id)}
                title={item.hint}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors border ${
                  viewId === item.id
                    ? 'bg-[#5b21b6] text-white border-[#7c3aed]'
                    : 'bg-[#1a1025] text-[#a78bfa] border-[#4c1d95] hover:text-white'
                }`}
              >
                {item.label}
              </button>
            ))}
          </>
        ) : null}
      </div>

      <div className="px-4 py-2 text-xs text-[#64748b] border-b border-[#212733] flex flex-wrap items-center justify-between gap-2">
        <span>{originHint}</span>
        {!isTerminalView(viewId) && editablePath && onOpenDiagramFile ? (
          <button
            type="button"
            onClick={() => onOpenDiagramFile(editablePath)}
            className="flex items-center gap-1 text-[#38bdf8] hover:underline"
          >
            <FileCode2 className="w-3.5 h-3.5" />
            {activeProjectDiagram?.origin === 'file' ? 'Редактировать схему' : 'Создать workflow.mmd'}
          </button>
        ) : null}
      </div>

      {error ? (
        <div className="px-4 py-2 text-xs text-amber-400">{error}</div>
      ) : null}

      <div className="flex-1 min-h-0">
        <MermaidDiagram source={diagramSource} className="h-full w-full" />
      </div>

      <div className="px-4 py-2 text-[10px] text-[#475569] border-t border-[#212733]">
        {terminalVisio
          ? 'Терминальный Visio включён — видны системные схемы CoreX.'
          : 'Показана только логика открытого проекта. Системные схемы: меню «Вид» → «Терминальный Visio».'}
      </div>
    </div>
  );
}
