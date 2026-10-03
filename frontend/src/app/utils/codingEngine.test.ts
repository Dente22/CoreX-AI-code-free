import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CODING_ENGINES,
  DEFAULT_CODING_ENGINE,
  codingEngineDescription,
  codingEngineLabel,
  getSavedCodingEngine,
  saveCodingEngineLocal,
} from './codingEngine';

describe('codingEngine', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal('window', {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => store.set(key, value),
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('lists Claude Code as the default first option and keeps Aider selectable', () => {
    expect(CODING_ENGINES.map((item) => item.id)).toEqual(['claude_code', 'aider', 'corex']);
    expect(DEFAULT_CODING_ENGINE).toBe('claude_code');
    expect(codingEngineLabel('claude_code')).toBe('Claude Code');
    expect(codingEngineLabel('aider')).toBe('Aider');
    expect(codingEngineLabel('corex')).toBe('CoreX агент');
  });

  it('falls back to Claude Code when nothing valid is saved', () => {
    expect(getSavedCodingEngine()).toBe('claude_code');
    window.localStorage.setItem('corex.codingEngine', 'unknown');
    expect(getSavedCodingEngine()).toBe('claude_code');
    saveCodingEngineLocal('aider');
    expect(getSavedCodingEngine()).toBe('aider');
  });

  it('explains how to plug OpenAI-only providers into Claude Code', () => {
    expect(codingEngineDescription('claude_code')).toContain('OmniRoute');
  });
});
