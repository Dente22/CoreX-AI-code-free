import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '../types/chatMessage';
import { applyChatDelta, finalizeStreaming, isOperationalChatNoise, shouldSkipDuplicateChat } from './chatStream';

function msg(partial: Partial<ChatMessage> & Pick<ChatMessage, 'id' | 'content'>): ChatMessage {
  return {
    role: 'assistant',
    timestamp: 'сейчас',
    ...partial,
  };
}

describe('applyChatDelta', () => {
  it('creates one streaming bubble then appends lines', () => {
    const first = applyChatDelta([], 'Соберу калькулятор', { id: 's1' });
    expect(first).toHaveLength(1);
    expect(first[0].streaming).toBe(true);
    expect(first[0].content).toBe('Соберу калькулятор');

    const withFile = [
      ...first,
      msg({ id: 'f1', content: 'Файл изменён: calculator.py' }),
    ];
    const next = applyChatDelta(withFile, 'Готово.');
    expect(next[0].content).toBe('Соберу калькулятор\nГотово.');
    expect(next[1].content).toContain('calculator.py');
  });
});

describe('finalizeStreaming', () => {
  it('clears streaming flag', () => {
    const done = finalizeStreaming([msg({ id: 's1', content: 'ok', streaming: true })]);
    expect(done[0].streaming).toBe(false);
  });
});

describe('shouldSkipDuplicateChat', () => {
  it('skips the same assistant text', () => {
    const messages = [msg({ id: 's1', content: 'Соберу калькулятор' })];
    expect(shouldSkipDuplicateChat(messages, 'Соберу калькулятор')).toBe(true);
    expect(shouldSkipDuplicateChat(messages, 'Файл изменён: calculator.py')).toBe(false);
  });
});

describe('isOperationalChatNoise', () => {
  it('hides pipeline banners and html dumps', () => {
    expect(isOperationalChatNoise('Лимиты отключены (эксперимент).')).toBe(true);
    expect(isOperationalChatNoise('База знаний: контекст «dev», языки: python')).toBe(true);
    expect(isOperationalChatNoise('Этап 1: UI/UX-дизайнер')).toBe(true);
    expect(isOperationalChatNoise('Конвейер готов.')).toBe(false);
    expect(isOperationalChatNoise('Файл изменён: index.html')).toBe(false);
  });
});

describe('applyChatDelta', () => {
  it('ignores html dump chunks', () => {
    const first = applyChatDelta([], 'Сайт будет тёмным лендингом', { id: 's1' });
    const next = applyChatDelta(first, '<!DOCTYPE html>');
    expect(next[0].content).toBe('Сайт будет тёмным лендингом');
  });
});
