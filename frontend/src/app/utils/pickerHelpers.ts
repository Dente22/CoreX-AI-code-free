import type { PickerFilter, PickerItem } from '../components/SelectionPickerModal';
import type { Agent } from './agents';
import type { Persona } from './personas';
import type { Pipeline } from './pipelines';

export const AGENT_FILTERS: PickerFilter[] = [
  { id: 'all', label: 'Все' },
  { id: 'Разработка', label: 'Разработка' },
  { id: 'Тестирование', label: 'Тестирование' },
  { id: 'Ревью', label: 'Ревью' },
  { id: 'Безопасность', label: 'Безопасность' },
  { id: 'DevOps', label: 'DevOps' },
  { id: 'Архитектура', label: 'Архитектура' },
];

export function skillItemsFromPersonas(personas: Persona[]): PickerItem[] {
  return personas.map((p) => ({
    id: p.id,
    name: p.name,
    description: p.description,
    category_ru: p.category_ru,
    source: p.source,
  }));
}

export function buildSkillFilters(personas: Persona[]): PickerFilter[] {
  const filters: PickerFilter[] = [{ id: 'all', label: 'Все' }];
  const categories = [
    ...new Set(
      personas
        .filter((p) => p.source !== 'project' && p.category_ru)
        .map((p) => p.category_ru as string),
    ),
  ].sort((a, b) => a.localeCompare(b, 'ru'));

  categories.forEach((cat) => filters.push({ id: cat, label: cat }));

  if (personas.some((p) => p.source === 'project')) {
    filters.push({ id: 'mine', label: 'Мои' });
  }
  return filters;
}

export function buildAgentFilters(agents: Agent[]): PickerFilter[] {
  const filters: PickerFilter[] = [{ id: 'all', label: 'Все' }];
  const categories = [
    ...new Set(
      agents
        .filter((agent) => agent.category_ru && agent.category_ru !== 'Мои агенты')
        .map((agent) => agent.category_ru as string),
    ),
  ].sort((a, b) => a.localeCompare(b, 'ru'));

  categories.forEach((cat) => filters.push({ id: cat, label: cat }));

  if (agents.some((agent) => agent.source === 'project')) {
    filters.push({ id: 'mine', label: 'Мои' });
  }

  return filters;
}

export function agentItemsFromAgents(agents: Agent[]): PickerItem[] {
  return agents.map((a) => ({
    id: a.id,
    name: a.name,
    description: a.description,
    category_ru: a.category_ru,
    source: a.source,
  }));
}

export function teamItemsFromPipelines(pipelines: Pipeline[]): PickerItem[] {
  return pipelines.map((p) => ({
    id: p.id,
    name: p.name,
    description: p.description,
    category_ru: p.source === 'library' ? 'Команды CoreX' : 'Мои команды',
    meta: `${p.steps_count} этапов · ${(p.step_labels || []).join(' → ')}`,
    source: p.source,
  }));
}

export function buildTeamFilters(pipelines: Pipeline[]): PickerFilter[] {
  const filters: PickerFilter[] = [{ id: 'all', label: 'Все' }];
  if (pipelines.some((p) => p.source === 'library')) {
    filters.push({ id: 'corex', label: 'Команды CoreX' });
  }
  if (pipelines.some((p) => p.source === 'project')) {
    filters.push({ id: 'mine', label: 'Мои' });
  }
  return filters;
}
