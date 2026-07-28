import { describe, it, expect } from 'vitest';
import { buildAgentFilters } from './pickerHelpers';
import type { Agent } from '../utils/agents';

describe('buildAgentFilters', () => {
  it('adds mine filter when project agents exist', () => {
    const agents: Agent[] = [
      { id: 'agent:lead-developer', name: 'Dev', description: '', source: 'library', category_ru: 'Разработка' },
      { id: 'agent:my_bot', name: 'My', description: '', source: 'project', category_ru: 'Мои агенты' },
    ];
    const filters = buildAgentFilters(agents);
    expect(filters.some((f) => f.id === 'mine')).toBe(true);
    expect(filters.some((f) => f.id === 'Разработка')).toBe(true);
  });
});
