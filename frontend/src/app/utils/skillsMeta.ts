import { fetchApi } from './api';

export interface SkillCategory {
  id: string;
  name: string;
  hint: string;
}

export interface TeamPreset {
  id: string;
  name: string;
  description: string;
  categories: string[];
}

let cachedCategories: SkillCategory[] | null = null;

export async function fetchSkillCategories(): Promise<SkillCategory[]> {
  if (cachedCategories) {
    return cachedCategories;
  }
  const response = await fetchApi('/api/skills/meta');
  if (!response.ok) {
    return [];
  }
  const data = await response.json();
  if (!data?.success || !Array.isArray(data.categories)) {
    return [];
  }
  cachedCategories = data.categories as SkillCategory[];
  return cachedCategories;
}

export async function fetchTeamPresets(): Promise<TeamPreset[]> {
  const response = await fetchApi('/api/skills/meta');
  if (!response.ok) {
    return [];
  }
  const data = await response.json();
  if (!data?.success || !Array.isArray(data.team_presets)) {
    return [];
  }
  return data.team_presets as TeamPreset[];
}
