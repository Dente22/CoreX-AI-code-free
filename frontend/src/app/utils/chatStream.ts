import type { ChatMessage } from '../types/chatMessage';

function streamId(): string {
  return `stream-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

export function isAiderDumpLine(text: string): boolean {
  const t = (text ?? '').trim();
  if (!t) {
    return false;
  }
  if (/^```/.test(t)) {
    return true;
  }
  if (/^<!DOCTYPE/i.test(t) || /^<\/?[a-zA-Z!]/.test(t)) {
    return true;
  }
  if (/^[.#@]?[a-zA-Z][\w-]*\s*\{/.test(t)) {
    return true;
  }
  if (/Can't initialize prompt toolkit|Summarization failed|file not found error/i.test(t)) {
    return true;
  }
  if (/^Dropping .+ from the chat/i.test(t) || /Has it been deleted from the file system/i.test(t)) {
    return true;
  }
  if (/^#{1,6}\s+\S+\.(html|css|js|py)\b/i.test(t)) {
    return true;
  }
  return false;
}

export function isOperationalChatNoise(content: string): boolean {
  const t = (content ?? '').trim();
  if (!t) {
    return true;
  }
  if (/^Лимиты отключены/.test(t)) {
    return true;
  }
  if (/^База знаний:/.test(t)) {
    return true;
  }
  if (/^Этап \d+:/.test(t)) {
    return true;
  }
  if (/^Design fallback:/.test(t)) {
    return true;
  }
  if (/^Нагрузка\s*\(/i.test(t)) {
    return true;
  }
  if (/Can't initialize prompt toolkit|Summarization failed/i.test(t)) {
    return true;
  }
  if (/file not found error/i.test(t) && /Dropping /i.test(t)) {
    return true;
  }
  if (/<!DOCTYPE html>/i.test(t) || /```(?:html|css|javascript|diff)/i.test(t)) {
    return true;
  }
  if (/^Конвейер завершён\./.test(t) && (t.includes('```') || t.length > 400)) {
    return true;
  }
  return false;
}

export function applyChatDelta(
  messages: ChatMessage[],
  text: string,
  options?: { model?: string; id?: string },
): ChatMessage[] {
  const chunk = (text ?? '').trimEnd();
  if (!chunk) {
    return messages;
  }
  if (isAiderDumpLine(chunk) || isOperationalChatNoise(chunk)) {
    return messages;
  }

  const idx = messages.findIndex((message) => message.role === 'assistant' && message.streaming);
  if (idx >= 0) {
    const current = messages[idx];
    const sep = !current.content || current.content.endsWith('\n') ? '' : '\n';
    const next = [...messages];
    next[idx] = {
      ...current,
      content: current.content ? `${current.content}${sep}${chunk}` : chunk,
      ...(options?.model && !current.model ? { model: options.model } : {}),
    };
    return next;
  }

  return [
    ...messages,
    {
      id: options?.id ?? streamId(),
      role: 'assistant',
      content: chunk,
      timestamp: 'только что',
      streaming: true,
      ...(options?.model ? { model: options.model } : {}),
    },
  ];
}

export function finalizeStreaming(messages: ChatMessage[]): ChatMessage[] {
  if (!messages.some((message) => message.streaming)) {
    return messages;
  }
  return messages.map((message) => (message.streaming ? { ...message, streaming: false } : message));
}

export function shouldSkipDuplicateChat(messages: ChatMessage[], content: string): boolean {
  const text = (content ?? '').trim();
  if (!text) {
    return true;
  }
  const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant');
  return Boolean(lastAssistant && lastAssistant.content.trim() === text);
}
