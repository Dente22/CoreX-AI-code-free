import { fetchApi } from './api';
import type { TraceErrorRecord, TraceEvent } from '../types/trace';

export async function fetchTraceErrors(taskId?: string | null): Promise<TraceErrorRecord[]> {
  const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : '';
  const response = await fetchApi(`/api/trace/errors${query}`);
  if (!response.ok) {
    return [];
  }
  const data = (await response.json()) as { errors?: TraceErrorRecord[] };
  return Array.isArray(data.errors) ? data.errors : [];
}

export async function fetchTraceTaskEvents(taskId: string): Promise<TraceEvent[]> {
  const response = await fetchApi(`/api/trace/task/${encodeURIComponent(taskId)}`);
  if (!response.ok) {
    return [];
  }
  const data = (await response.json()) as { events?: TraceEvent[] };
  return Array.isArray(data.events) ? data.events : [];
}

export async function fetchTraceEventDetail(taskId: string, eventId: string): Promise<TraceEvent | null> {
  const response = await fetchApi(
    `/api/trace/task/${encodeURIComponent(taskId)}/event/${encodeURIComponent(eventId)}`,
  );
  if (!response.ok) {
    return null;
  }
  const data = (await response.json()) as { event?: TraceEvent };
  return data.event ?? null;
}
