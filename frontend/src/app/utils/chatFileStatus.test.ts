import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '../types/chatMessage';
import {
  fileWordRu,
  groupChatMessages,
  isFileStatusContent,
  isStubReportContent,
  parseFileStatus,
} from './chatFileStatus';

function msg(id: string, role: ChatMessage['role'], content: string): ChatMessage {
  return { id, role, content, timestamp: 'сейчас' };
}

describe('isFileStatusContent', () => {
  it('matches short file events', () => {
    expect(isFileStatusContent('Файл записан: style.css -> D:\\TEST\\style.css')).toBe(true);
    expect(isFileStatusContent('Файл создан: index.html')).toBe(true);
    expect(isFileStatusContent('Файл изменён (patch): main.py [replace@3]')).toBe(true);
    expect(isFileStatusContent('Файл изменён: calculator.py')).toBe(true);
    expect(isFileStatusContent('Проверка кода OK: main.py (syntax)')).toBe(true);
  });

  it('ignores normal replies', () => {
    expect(isFileStatusContent('Изменил style.css, сайт теперь выглядит лучше.')).toBe(false);
    expect(isFileStatusContent('Краткий отчёт на русском')).toBe(false);
  });
});

describe('isStubReportContent', () => {
  it('matches the placeholder done line', () => {
    expect(isStubReportContent('краткий отчёт на русском')).toBe(true);
    expect(isStubReportContent('Краткий отчет на русском.')).toBe(true);
  });

  it('keeps a real summary', () => {
    expect(isStubReportContent('Сайт готов: index.html, style.css и script.js.')).toBe(false);
  });
});

describe('parseFileStatus', () => {
  it('reads name before arrow', () => {
    const parsed = parseFileStatus('Файл записан: style.css -> D:\\TEST\\TEST1\\style.css');
    expect(parsed.name).toBe('style.css');
    expect(parsed.path).toBe('style.css');
    expect(parsed.action).toBe('записан');
  });

  it('reads patch path', () => {
    const parsed = parseFileStatus('Файл изменён (patch): src/app.ts [replace@1]');
    expect(parsed.name).toBe('app.ts');
    expect(parsed.path).toBe('src/app.ts');
    expect(parsed.action).toBe('изменён');
  });
});

describe('fileWordRu', () => {
  it('uses Russian plural forms', () => {
    expect(fileWordRu(1)).toBe('файл');
    expect(fileWordRu(2)).toBe('файла');
    expect(fileWordRu(5)).toBe('файлов');
    expect(fileWordRu(21)).toBe('файл');
  });
});

describe('groupChatMessages', () => {
  it('collapses consecutive file events and keeps chat around them', () => {
    const items = groupChatMessages([
      msg('u1', 'user', 'Сделай сайт'),
      msg('a1', 'assistant', 'Файл записан: index.html -> D:\\p\\index.html'),
      msg('a2', 'assistant', 'Файл записан: style.css -> D:\\p\\style.css'),
      msg('a3', 'assistant', 'Файл записан: script.js -> D:\\p\\script.js'),
      msg('a4', 'assistant', 'краткий отчёт на русском'),
    ]);

    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'message' });
    expect(items[1]).toMatchObject({ kind: 'file_group' });
    if (items[1].kind === 'file_group') {
      expect(items[1].files.map((file) => file.name)).toEqual([
        'index.html',
        'style.css',
        'script.js',
      ]);
    }
  });

  it('drops a stub report when there are no files', () => {
    const items = groupChatMessages([
      msg('u1', 'user', 'Сделай сайт'),
      msg('a1', 'assistant', 'краткий отчёт на русском'),
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ kind: 'message' });
  });

  it('drops memory-only writes so chat/ stays hidden', () => {
    const items = groupChatMessages([
      msg('u1', 'user', 'Сделай сайт'),
      msg('a1', 'assistant', 'Файл записан: chat/project_memory.md -> D:\\p\\chat\\project_memory.md'),
      msg('a2', 'assistant', 'краткий отчёт на русском'),
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ kind: 'message' });
  });

  it('keeps real files and hides chat/ writes in the same group', () => {
    const items = groupChatMessages([
      msg('a1', 'assistant', 'Файл записан: index.html -> D:\\p\\index.html'),
      msg('a2', 'assistant', 'Файл записан: chat/project_memory.md -> D:\\p\\chat\\project_memory.md'),
    ]);
    expect(items).toHaveLength(1);
    if (items[0].kind === 'file_group') {
      expect(items[0].files.map((file) => file.path)).toEqual(['index.html']);
    }
  });

  it('merges write + verify of the same file', () => {
    const items = groupChatMessages([
      msg('a1', 'assistant', 'Файл записан: main.py -> D:\\p\\main.py'),
      msg('a2', 'assistant', 'Проверка кода OK: main.py (syntax)'),
    ]);
    expect(items).toHaveLength(1);
    if (items[0].kind === 'file_group') {
      expect(items[0].files).toHaveLength(1);
      expect(items[0].files[0].action).toBe('проверен');
    }
  });
});
