import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  FileCode2,
  Loader2,
  MessageSquare,
  Radio,
  Route,
  Wrench,
  XCircle,
  type LucideIcon,
} from 'lucide-react';
import { useChat } from '../contexts/ChatContext';
import {
  TRACE_PIPELINE,
  type TraceEvent,
  type TraceEventDetail,
  type TraceNodeId,
  type TraceStatus,
} from '../types/trace';
import { fetchTraceEventDetail } from '../utils/traceApi';

const NODE_ICONS: Record<TraceNodeId, LucideIcon> = {
  request: MessageSquare,
  ws: Radio,
  plan: Route,
  llm: Cpu,
  tool: Wrench,
  editor: FileCode2,
  response: CheckCircle2,
};

const STATUS_COLORS: Record<TraceStatus, string> = {
  waiting: 'var(--corex-text-dim)',
  active: 'var(--corex-spark)',
  done: '#34d399',
  error: '#f87171',
};

type TraceTab = 'chain' | 'errors';

function formatElapsed(startTs: number | null) {
  if (!startTs) return '—';
  const sec = Math.max(0, (Date.now() - startTs * 1000) / 1000);
  if (sec < 60) return `${sec.toFixed(1)} с`;
  return `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;
}

function nodeStatus(events: TraceEvent[], nodeId: TraceNodeId): TraceStatus {
  const nodeEvents = events.filter((e) => e.node === nodeId);
  if (nodeEvents.length === 0) return 'waiting';
  const last = nodeEvents[nodeEvents.length - 1];
  return last.status;
}

function detailLanguage(detail: TraceEventDetail): string {
  if (detail.language) return detail.language;
  if (detail.kind === 'llm_response' || detail.kind === 'tool_request') return 'json';
  return 'text';
}

function TraceDetailBody({ detail }: { detail: TraceEventDetail }) {
  const sections: { label: string; content: string; lang: string }[] = [];

  if (detail.body) {
    sections.push({ label: detail.title || 'Содержимое', content: detail.body, lang: detailLanguage(detail) });
  }
  if (detail.arguments && Object.keys(detail.arguments).length > 0) {
    sections.push({
      label: 'Аргументы',
      content: JSON.stringify(detail.arguments, null, 2),
      lang: 'json',
    });
  }
  if (detail.result && Object.keys(detail.result).length > 0) {
    sections.push({
      label: 'Результат',
      content: JSON.stringify(detail.result, null, 2),
      lang: 'json',
    });
  }
  if (detail.request && Object.keys(detail.request).length > 0) {
    sections.push({
      label: 'Запрос',
      content: JSON.stringify(detail.request, null, 2),
      lang: 'json',
    });
  }

  if (sections.length === 0) {
    return <p className="text-xs text-[var(--corex-text-dim)]">Нет деталей для этого шага.</p>;
  }

  return (
    <div className="corex-trace-detail-stack">
      {detail.path && (
        <div className="text-[10px] font-mono text-[var(--corex-spark)] mb-2 truncate">{detail.path}</div>
      )}
      {sections.map((section) => (
        <div key={section.label} className="corex-trace-detail-block">
          <div className="corex-trace-detail-label">{section.label}</div>
          <pre className={`corex-trace-detail-pre language-${section.lang}`}>{section.content}</pre>
        </div>
      ))}
      {detail.truncated && (
        <p className="text-[10px] text-amber-400/90 mt-1">Показана укороченная версия. Полная — в chat/trace/ на диске.</p>
      )}
    </div>
  );
}

function FlowNode({
  id,
  label,
  status,
  isLast,
}: {
  id: TraceNodeId;
  label: string;
  status: TraceStatus;
  isLast: boolean;
}) {
  const Icon = NODE_ICONS[id];
  const color = STATUS_COLORS[status];

  return (
    <div className="corex-trace-node-wrap">
      <div
        className={`corex-trace-node ${status === 'active' ? 'corex-trace-node--pulse' : ''}`}
        style={{ borderColor: color, boxShadow: status === 'active' ? `0 0 20px ${color}44` : undefined }}
      >
        <Icon className="w-4 h-4" style={{ color }} />
        <span className="text-[10px] font-semibold text-[var(--corex-text-muted)] mt-1">{label}</span>
        {status === 'active' && <Loader2 className="w-3 h-3 animate-spin absolute top-1 right-1 text-[var(--corex-spark)]" />}
        {status === 'error' && <XCircle className="w-3 h-3 absolute top-1 right-1 text-red-400" />}
        {status === 'done' && <span className="corex-trace-node-dot" style={{ background: color }} />}
      </div>
      {!isLast && (
        <div className="corex-trace-connector">
          <div className="corex-trace-connector-line" />
        </div>
      )}
    </div>
  );
}

function ChainNode({
  event,
  isActive,
  isHighlighted,
  isExpanded,
  onToggle,
  detailOverride,
  loadingDetail,
  nodeRef,
}: {
  event: TraceEvent;
  isActive: boolean;
  isHighlighted: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  detailOverride?: TraceEventDetail;
  loadingDetail: boolean;
  nodeRef?: (el: HTMLDivElement | null) => void;
}) {
  const Icon = NODE_ICONS[event.node] ?? Activity;
  const color = STATUS_COLORS[event.status];
  const detail = detailOverride ?? event.detail;
  const hasDetail = Boolean(detail && (detail.body || detail.arguments || detail.result));

  return (
    <div
      ref={nodeRef}
      className={`corex-trace-chain-item ${isActive ? 'corex-trace-chain-item--active' : ''} ${isHighlighted ? 'corex-trace-chain-item--highlight' : ''}`}
    >
      <div className="corex-trace-chain-rail">
        <div className="corex-trace-chain-dot" style={{ background: color, boxShadow: `0 0 8px ${color}66` }} />
        <div className="corex-trace-chain-line" />
      </div>
      <div className="corex-trace-chain-card" style={{ borderColor: `${color}44` }}>
        <button type="button" className="corex-trace-chain-header" onClick={onToggle}>
          <div className="flex items-center gap-2 min-w-0 flex-1">
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5 shrink-0 text-[var(--corex-text-dim)]" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 shrink-0 text-[var(--corex-text-dim)]" />
            )}
            <Icon className="w-3.5 h-3.5 shrink-0" style={{ color }} />
            <span className="text-xs font-medium text-[var(--corex-text)] truncate">{event.label}</span>
            <span className="text-[9px] uppercase tracking-wider text-[var(--corex-text-dim)] ml-auto shrink-0">
              {event.kind}
            </span>
          </div>
        </button>
        {event.meta && Object.keys(event.meta).length > 0 && (
          <div className="corex-trace-meta-row">
            {event.meta.model != null && (
              <span className="corex-trace-chip corex-trace-chip--model">{String(event.meta.model)}</span>
            )}
            {event.meta.tool != null && (
              <span className="corex-trace-chip">
                {event.meta.server != null ? `${String(event.meta.server)}.` : ''}
                {String(event.meta.tool)}
              </span>
            )}
            {event.meta.path != null && (
              <span className="corex-trace-chip corex-trace-chip--path">{String(event.meta.path)}</span>
            )}
            {event.meta.chars != null && (
              <span className="corex-trace-chip">{String(event.meta.chars)} симв.</span>
            )}
          </div>
        )}
        {isExpanded && (
          <div className="corex-trace-detail-panel">
            {loadingDetail && (
              <div className="flex items-center gap-2 text-xs text-[var(--corex-text-dim)] py-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Загрузка полной версии…
              </div>
            )}
            {!loadingDetail && hasDetail && detail && <TraceDetailBody detail={detail} />}
            {!loadingDetail && !hasDetail && (
              <p className="text-xs text-[var(--corex-text-dim)] py-1">Детали появятся после следующих шагов задачи.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AdminTracePanel() {
  const {
    traceEvents,
    traceTaskId,
    traceErrors,
    highlightTraceEventId,
    jumpToTraceEvent,
    refreshTraceErrors,
    isThinking,
    clearTrace,
    connectionStatus,
  } = useChat();

  const chainRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [activeTab, setActiveTab] = useState<TraceTab>('chain');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [detailCache, setDetailCache] = useState<Record<string, TraceEventDetail>>({});
  const [loadingDetailId, setLoadingDetailId] = useState<string | null>(null);

  const taskEvents = useMemo(
    () => (traceTaskId ? traceEvents.filter((e) => e.task_id === traceTaskId) : traceEvents),
    [traceEvents, traceTaskId],
  );

  const taskErrors = useMemo(
    () => (traceTaskId ? traceErrors.filter((e) => e.task_id === traceTaskId) : traceErrors),
    [traceErrors, traceTaskId],
  );

  const startTs = taskEvents[0]?.ts ?? null;
  const modelLabel = useMemo(() => {
    const llm = [...taskEvents].reverse().find((e) => e.meta?.model);
    return llm?.meta?.model ? String(llm.meta.model) : '—';
  }, [taskEvents]);

  useEffect(() => {
    chainRef.current?.scrollTo({ top: chainRef.current.scrollHeight, behavior: 'smooth' });
  }, [taskEvents.length]);

  useEffect(() => {
    if (!highlightTraceEventId) {
      return;
    }
    setActiveTab('chain');
    setExpandedIds((prev) => new Set(prev).add(highlightTraceEventId));
    const node = nodeRefs.current[highlightTraceEventId];
    node?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [highlightTraceEventId]);

  const toggleExpand = useCallback(
    async (event: TraceEvent) => {
      const next = new Set(expandedIds);
      if (next.has(event.id)) {
        next.delete(event.id);
        setExpandedIds(next);
        return;
      }
      next.add(event.id);
      setExpandedIds(next);

      const cached = detailCache[event.id];
      const wsDetail = event.detail;
      const needsFetch =
        traceTaskId &&
        (!wsDetail?.body || wsDetail.truncated) &&
        !cached;

      if (needsFetch) {
        setLoadingDetailId(event.id);
        try {
          const full = await fetchTraceEventDetail(traceTaskId, event.id);
          if (full?.detail) {
            setDetailCache((prev) => ({ ...prev, [event.id]: full.detail! }));
          }
        } finally {
          setLoadingDetailId(null);
        }
      }
    },
    [detailCache, expandedIds, traceTaskId],
  );

  const goToError = useCallback(
    (eventId: string) => {
      jumpToTraceEvent(eventId);
    },
    [jumpToTraceEvent],
  );

  return (
    <div className="corex-trace-panel h-full flex flex-col min-h-0">
      <div className="corex-panel-header">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[var(--corex-brand)]" />
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--corex-text)]">
            Нейротрасса AI
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full border ${
              connectionStatus === 'open'
                ? 'border-emerald-500/40 text-emerald-400'
                : 'border-[var(--corex-border)] text-[var(--corex-text-dim)]'
            }`}
          >
            {connectionStatus === 'open' ? 'WS подключён' : connectionStatus}
          </span>
          {isThinking && (
            <span className="text-[10px] text-[var(--corex-spark)] flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              выполняется
            </span>
          )}
          <button type="button" onClick={() => void refreshTraceErrors()} className="corex-icon-btn text-[10px] px-2">
            ↻
          </button>
          <button type="button" onClick={clearTrace} className="corex-icon-btn text-[10px] px-2">
            Очистить
          </button>
        </div>
      </div>

      <div className="corex-trace-tabs">
        <button
          type="button"
          className={`corex-trace-tab ${activeTab === 'chain' ? 'corex-trace-tab--active' : ''}`}
          onClick={() => setActiveTab('chain')}
        >
          Цепочка
        </button>
        <button
          type="button"
          className={`corex-trace-tab ${activeTab === 'errors' ? 'corex-trace-tab--active' : ''}`}
          onClick={() => setActiveTab('errors')}
        >
          Ошибки
          {taskErrors.length > 0 && <span className="corex-trace-tab-badge">{taskErrors.length}</span>}
        </button>
      </div>

      <div className="corex-trace-stats">
        <div>
          <span className="corex-trace-stat-label">Задача</span>
          <span className="corex-trace-stat-value font-mono">{traceTaskId || '—'}</span>
        </div>
        <div>
          <span className="corex-trace-stat-label">Модель</span>
          <span className="corex-trace-stat-value">{modelLabel}</span>
        </div>
        <div>
          <span className="corex-trace-stat-label">Время</span>
          <span className="corex-trace-stat-value">{formatElapsed(startTs)}</span>
        </div>
        <div>
          <span className="corex-trace-stat-label">События</span>
          <span className="corex-trace-stat-value">{taskEvents.length}</span>
        </div>
      </div>

      {activeTab === 'chain' && (
        <div className="corex-trace-pipeline px-4 py-5 border-b border-[var(--corex-border)] overflow-x-auto">
          <div className="flex items-center min-w-max mx-auto">
            {TRACE_PIPELINE.map((stage, index) => (
              <FlowNode
                key={stage.id}
                id={stage.id}
                label={stage.label}
                status={nodeStatus(taskEvents, stage.id)}
                isLast={index === TRACE_PIPELINE.length - 1}
              />
            ))}
          </div>
        </div>
      )}

      <div ref={chainRef} className="flex-1 min-h-0 overflow-y-auto p-4">
        {activeTab === 'errors' ? (
          taskErrors.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-6">
              <CheckCircle2 className="w-10 h-10 text-emerald-400/60 mb-3" />
              <p className="text-sm text-[var(--corex-text)]">Ошибок пока нет</p>
              <p className="text-xs text-[var(--corex-text-muted)] mt-1">
                Журнал сохраняется в chat/trace/errors.jsonl
              </p>
            </div>
          ) : (
            <div className="corex-trace-errors-list">
              {[...taskErrors].reverse().map((err) => (
                <div key={err.id} className="corex-trace-error-card">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-[var(--corex-text)]">{err.label}</div>
                      <div className="text-[11px] text-red-300/90 mt-1 break-words">{err.message}</div>
                      <div className="text-[9px] text-[var(--corex-text-dim)] mt-1 uppercase">{err.kind} · {err.node}</div>
                    </div>
                    <button
                      type="button"
                      className="corex-trace-jump-btn"
                      onClick={() => goToError(err.event_id)}
                    >
                      Перейти
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : taskEvents.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <Route className="w-10 h-10 text-[var(--corex-brand)] opacity-50 mb-3" />
            <p className="text-sm text-[var(--corex-text)] font-medium mb-1">Ожидание запроса к AI</p>
            <p className="text-xs text-[var(--corex-text-muted)] max-w-sm">
              Отправьте сообщение — раскройте любой шаг, чтобы увидеть запрос, код или результат инструмента
            </p>
          </div>
        ) : (
          <div className="corex-trace-chain">
            {taskEvents.map((event, index) => (
              <ChainNode
                key={event.id}
                event={event}
                isActive={index === taskEvents.length - 1 && event.status === 'active'}
                isHighlighted={highlightTraceEventId === event.id}
                isExpanded={expandedIds.has(event.id)}
                onToggle={() => void toggleExpand(event)}
                detailOverride={detailCache[event.id]}
                loadingDetail={loadingDetailId === event.id}
                nodeRef={(el) => {
                  nodeRefs.current[event.id] = el;
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
