import { fetchApi } from './api';
import type { ChatMessage } from '../types/chatMessage';

export interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
  preview: string;
}

function toChatMessage(raw: Record<string, unknown>, index: number): ChatMessage | null {
  const role = raw.role;
  if (role !== 'user' && role !== 'assistant') {
    return null;
  }
  const content = typeof raw.content === 'string' ? raw.content : String(raw.content ?? '').trim();
  if (!content) {
    return null;
  }
  return {
    id: typeof raw.id === 'string' && raw.id ? raw.id : `saved-${index}-${Date.now()}`,
    role,
    content,
    timestamp: typeof raw.timestamp === 'string' ? raw.timestamp : 'сохранено',
  };
}

export async function fetchChatMessages(): Promise<ChatMessage[]> {
  const response = await fetchApi('/api/chat/messages');
  if (!response.ok) return [];
  const data = await response.json();
  if (!data?.success || !Array.isArray(data.messages)) return [];
  return data.messages
    .map((msg: Record<string, unknown>, index: number) => toChatMessage(msg, index))
    .filter((msg: ChatMessage | null): msg is ChatMessage => msg !== null);
}

export async function saveChatMessages(messages: ChatMessage[]): Promise<void> {
  const payload = messages.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    timestamp: m.timestamp,
  }));
  await fetchApi('/api/chat/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: payload }),
  });
}

export async function fetchChatSessions(): Promise<ChatSessionSummary[]> {
  const response = await fetchApi('/api/chat/sessions');
  if (!response.ok) return [];
  const data = await response.json();
  if (!data?.success || !Array.isArray(data.sessions)) return [];
  return data.sessions as ChatSessionSummary[];
}

export async function fetchChatSession(sessionId: string): Promise<ChatMessage[]> {
  const response = await fetchApi(`/api/chat/sessions/${encodeURIComponent(sessionId)}`);
  if (!response.ok) return [];
  const data = await response.json();
  const messages = data?.session?.messages;
  if (!Array.isArray(messages)) return [];
  return messages
    .map((msg: Record<string, unknown>, index: number) => toChatMessage(msg, index))
    .filter((msg: ChatMessage | null): msg is ChatMessage => msg !== null);
}

export async function archiveChatSession(messages: ChatMessage[]): Promise<ChatSessionSummary | null> {
  const payload = messages.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    timestamp: m.timestamp,
  }));
  const response = await fetchApi('/api/chat/archive', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: payload }),
  });
  const data = await response.json();
  if (!response.ok || !data?.success) return null;
  return data.session as ChatSessionSummary;
}

export function formatSessionDate(iso: string): string {
  if (!iso) return '';
  try {
    const date = new Date(iso);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}
