import type { ChatMessage } from '../types/chatMessage';
import { isCorexInternalPath } from './corexInternal';

const FILE_STATUS_START =
  /^(Файл (?:создан|записан|обновлён|обновлен|изменён|изменен)|Создана заготовка|Авто-исправление|Проверка кода OK)(?=\s|:|$|\()/i;

export interface FileStatusEntry {
  id: string;
  action: string;
  name: string;
  path: string;
  content: string;
}

export type ChatListItem =
  | { kind: 'message'; message: ChatMessage }
  | { kind: 'file_group'; id: string; messages: ChatMessage[]; files: FileStatusEntry[] };

export function isFileStatusContent(content: string): boolean {
  const text = (content ?? '').trim();
  if (!text || text.length > 500) {
    return false;
  }
  if ((text.match(/\n/g) ?? []).length > 2) {
    return false;
  }
  return FILE_STATUS_START.test(text);
}

export function isStubReportContent(content: string): boolean {
  const text = (content ?? '')
    .trim()
    .replace(/[.…]+$/g, '')
    .trim();
  return /^краткий отч[её]т на русском$/i.test(text)
    || /^brief report in russian$/i.test(text);
}

function foldsIntoFileGroup(message: ChatMessage): boolean {
  if ((message?.role ?? 'assistant') !== 'assistant') {
    return false;
  }
  const content = message?.content ?? '';
  return isFileStatusContent(content) || isStubReportContent(content);
}

export function fileWordRu(count: number): string {
  const n10 = count % 10;
  const n100 = count % 100;
  if (n10 === 1 && n100 !== 11) {
    return 'файл';
  }
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) {
    return 'файла';
  }
  return 'файлов';
}

function basename(value: string): string {
  const cleaned = value.trim().replace(/\\/g, '/');
  const parts = cleaned.split('/');
  return parts[parts.length - 1] || cleaned;
}

function actionFrom(text: string): string {
  if (/Проверка кода OK/i.test(text)) {
    return 'проверен';
  }
  if (/записан/i.test(text)) {
    return 'записан';
  }
  if (/создан/i.test(text)) {
    return 'создан';
  }
  if (/обновл/i.test(text)) {
    return 'обновлён';
  }
  if (/измен/i.test(text)) {
    return 'изменён';
  }
  if (/заготовка/i.test(text)) {
    return 'заготовка';
  }
  if (/Авто-исправление/i.test(text)) {
    return 'исправление';
  }
  return 'изменён';
}

export function parseFileStatus(content: string): Omit<FileStatusEntry, 'id' | 'content'> {
  const text = (content ?? '').trim();
  const arrow = text.match(/:\s*(.+?)\s+->\s+(.+)$/);
  if (arrow) {
    const left = arrow[1].trim();
    return {
      action: actionFrom(text),
      name: basename(left),
      path: left,
    };
  }

  const afterColon = text.match(/:\s*(.+)$/);
  if (afterColon) {
    const rest = afterColon[1]
      .replace(/\s+[—–-]\s+.*$/, '')
      .replace(/\s+\[[^\]]*\]\s*$/, '')
      .replace(/\s+\([^)]*\)\s*$/, '')
      .trim();
    return {
      action: actionFrom(text),
      name: basename(rest),
      path: rest,
    };
  }

  return {
    action: actionFrom(text),
    name: text.slice(0, 48),
    path: '',
  };
}

function uniqueFiles(messages: ChatMessage[]): FileStatusEntry[] {
  const map = new Map<string, FileStatusEntry>();
  for (const message of messages) {
    const content = message.content ?? '';
    if (isStubReportContent(content) || !isFileStatusContent(content)) {
      continue;
    }
    const parsed = parseFileStatus(content);
    if (isCorexInternalPath(parsed.path) || isCorexInternalPath(parsed.name)) {
      continue;
    }
    const key = (parsed.path || parsed.name || message.id).toLowerCase();
    map.set(key, {
      ...parsed,
      id: message.id,
      content,
    });
  }
  return [...map.values()];
}

export function groupChatMessages(messages: ChatMessage[]): ChatListItem[] {
  const items: ChatListItem[] = [];
  let bucket: ChatMessage[] = [];

  const flush = () => {
    if (bucket.length === 0) {
      return;
    }
    const files = uniqueFiles(bucket);
    if (files.length > 0) {
      items.push({
        kind: 'file_group',
        id: `files-${bucket[0].id}`,
        messages: bucket,
        files,
      });
    }
    bucket = [];
  };

  for (const message of messages) {
    if (foldsIntoFileGroup(message)) {
      bucket.push(message);
      continue;
    }
    flush();
    items.push({ kind: 'message', message });
  }
  flush();
  return items;
}
