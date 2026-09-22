import { describe, expect, it } from 'vitest';
import { CODING_ENGINES, codingEngineLabel } from './codingEngine';

describe('codingEngine', () => {
  it('lists aider as default first option', () => {
    expect(CODING_ENGINES[0]?.id).toBe('aider');
    expect(codingEngineLabel('aider')).toBe('Aider');
    expect(codingEngineLabel('corex')).toBe('CoreX агент');
  });
});
