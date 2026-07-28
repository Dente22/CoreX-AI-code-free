export type TraceNodeId =
  | 'request'
  | 'ws'
  | 'plan'
  | 'llm'
  | 'tool'
  | 'editor'
  | 'response';

export type TraceStatus = 'active' | 'done' | 'error' | 'waiting';

export type TraceDetailKind =
  | 'llm_request'
  | 'llm_response'
  | 'tool_request'
  | 'tool_response'
  | 'file_content'
  | 'error'
  | 'plan'
  | 'generic';

export interface TraceEventDetail {
  kind: TraceDetailKind | string;
  title?: string;
  body?: string;
  language?: string;
  path?: string;
  truncated?: boolean;
  request?: Record<string, unknown>;
  response?: Record<string, unknown>;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
}

export interface TraceEvent {
  id: string;
  task_id: string;
  ts: number;
  phase: string;
  kind: string;
  label: string;
  status: TraceStatus;
  node: TraceNodeId;
  parent?: string | null;
  meta?: Record<string, unknown>;
  detail?: TraceEventDetail;
}

export interface TraceErrorRecord {
  id: string;
  task_id: string;
  event_id: string;
  ts: number;
  label: string;
  message: string;
  kind: string;
  node: TraceNodeId;
}

export const TRACE_PIPELINE: { id: TraceNodeId; label: string }[] = [
  { id: 'request', label: 'Запрос' },
  { id: 'ws', label: 'WebSocket' },
  { id: 'plan', label: 'План' },
  { id: 'llm', label: 'Модель' },
  { id: 'tool', label: 'Инструмент' },
  { id: 'editor', label: 'Редактор' },
  { id: 'response', label: 'Ответ' },
];
