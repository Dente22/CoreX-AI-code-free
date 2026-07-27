import { fetchApi } from './api';
import type { Agent } from './agents';
import type { Persona } from './personas';
import type { Pipeline, WorkMode } from './pipelines';

export interface ProjectDiagram {
  id: string;
  label: string;
  path: string;
  source: string;
  origin: 'file' | 'generated';
  kind: 'diagram' | 'structure' | 'pipelines' | 'memory';
}

export interface VisioPayload {
  success: boolean;
  project_name: string;
  diagrams: ProjectDiagram[];
  system: {
    overview: string;
    architecture: string;
  };
  paths: {
    workflow: string;
    architecture: string;
    directory: string;
  };
}

export type TerminalVisioView = 'terminal:overview' | 'terminal:ai' | 'terminal:architecture';

export const TERMINAL_VISIO_VIEWS: {
  id: TerminalVisioView;
  label: string;
  hint: string;
}[] = [
  { id: 'terminal:overview', label: 'Обзор CoreX', hint: 'Как работает IDE' },
  { id: 'terminal:ai', label: 'AI-режим', hint: 'Текущий скил, агент или команда' },
  { id: 'terminal:architecture', label: 'Архитектура CoreX', hint: 'Системные компоненты' },
];

export type VisioViewId = string;

function mermaidLabel(text: string): string {
  return text.replace(/"/g, "'").replace(/[[\]{}]/g, '').slice(0, 80);
}

export async function fetchVisio(): Promise<VisioPayload | null> {
  try {
    const response = await fetchApi('/api/visio');
    if (!response.ok) return null;
    const data = (await response.json()) as VisioPayload;
    return data?.success ? data : null;
  } catch {
    return null;
  }
}

export function buildAiModeDiagram(
  workMode: WorkMode,
  personas: Persona[],
  agents: Agent[],
  pipelines: Pipeline[],
  selectedPersonaId: string,
  selectedAgentId: string,
  selectedPipelineId: string,
): string {
  if (workMode === 'pipeline') {
    const pipeline = pipelines.find((p) => p.id === selectedPipelineId);
    if (!pipeline) {
      return `flowchart LR
        start[Запрос пользователя] --> pick[Выберите команду в чате]
        pick --> run[Этапы команды]
        run --> files[Файлы проекта]`;
    }
    const labels = pipeline.step_labels?.length
      ? pipeline.step_labels
      : Array.from({ length: pipeline.steps_count }, (_, i) => `Этап ${i + 1}`);
    const lines = ['flowchart LR', '    user[Запрос пользователя] --> cmd["' + mermaidLabel(pipeline.name) + '"]'];
    let prev = 'cmd';
    labels.forEach((label, index) => {
      const nodeId = `step${index}`;
      lines.push(`    ${prev} --> ${nodeId}["${mermaidLabel(label)}"]`);
      prev = nodeId;
    });
    lines.push(`    ${prev} --> result[Результат в проекте]`);
    return lines.join('\n');
  }

  if (workMode === 'agent') {
    const agent = agents.find((a) => a.id === selectedAgentId);
    const name = agent?.name ?? 'Агент';
    return `flowchart TB
    user[Запрос пользователя] --> agent["${mermaidLabel(name)}"]
    agent --> plan[План задачи]
    plan --> skills[Скилы агента]
    skills --> write[Чтение / запись файлов]
    write --> answer[Ответ в чате]
    style agent fill:#4c1d95,stroke:#8b5cf6,color:#fff`;
  }

  const persona = personas.find((p) => p.id === selectedPersonaId);
  const name = persona?.name ?? 'Скил';
  return `flowchart LR
    user[Запрос] --> skill["${mermaidLabel(name)}"]
    skill --> tools[Инструменты CoreX]
    tools --> files[Файлы проекта]
    files --> reply[Ответ AI]
    style skill fill:#0f766e,stroke:#14b8a6,color:#fff`;
}

export function getDiagramSource(
  viewId: VisioViewId,
  payload: VisioPayload | null,
  aiDiagram: string,
): string {
  if (viewId === 'terminal:ai') return aiDiagram;
  if (viewId === 'terminal:overview') {
    return payload?.system.overview ?? `flowchart TB\n    wait[Нет данных]`;
  }
  if (viewId === 'terminal:architecture') {
    return payload?.system.architecture ?? `flowchart TB\n    wait[Нет данных]`;
  }

  const projectDiagram = payload?.diagrams.find((d) => d.id === viewId);
  if (projectDiagram?.source) return projectDiagram.source;

  if (!payload) {
    return `flowchart TB
      wait[Откройте проект] --> visio[Visio покажет логику проекта]`;
  }

  return payload.diagrams[0]?.source ?? `flowchart TB\n    empty[Нет диаграмм в проекте]`;
}

export function getDefaultProjectViewId(payload: VisioPayload | null): VisioViewId {
  if (!payload?.diagrams.length) return 'structure';
  const workflow = payload.diagrams.find((d) => d.id === 'workflow');
  return workflow?.id ?? payload.diagrams[0].id;
}

export function isTerminalView(viewId: VisioViewId): boolean {
  return viewId.startsWith('terminal:');
}
