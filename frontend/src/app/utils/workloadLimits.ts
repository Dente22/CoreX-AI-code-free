import { fetchApi } from './api';

export interface WorkloadLimitValues {
  max_total_turns: number;
  max_turns_per_step: number;
  max_file_writes: number;
  delay_between_turns_ms: number;
  delay_between_steps_ms: number;
}

export interface TeamStepTurnLimit {
  agent_id: string;
  role: string;
  default_max_turns: number;
}

export interface WorkloadLimitsSettings {
  slider: number;
  default_slider: number;
  tier: string;
  limits: WorkloadLimitValues;
  min_limits: WorkloadLimitValues;
  max_limits: WorkloadLimitValues;
  absolute_max_limits: WorkloadLimitValues;
  turns_limit_enabled?: boolean;
  turns_limit_mode?: 'team' | 'per_agent';
  team_max_total_turns?: number;
  team_max_turns_per_step?: number;
  per_agent_turns?: Record<string, number>;
  team_steps?: TeamStepTurnLimit[];
  team_pipeline_id?: string;
  unlimited_limits?: boolean;
  step_by_step_enabled?: boolean;
  design_folder_path?: string;
}

export interface WorkloadLimitsPayload {
  slider?: number;
  turns_limit_enabled?: boolean;
  turns_limit_mode?: 'team' | 'per_agent';
  team_max_total_turns?: number;
  team_max_turns_per_step?: number;
  per_agent_turns?: Record<string, number>;
  unlimited_limits?: boolean;
  step_by_step_enabled?: boolean;
  design_folder_path?: string;
}

export async function fetchWorkloadLimits(): Promise<WorkloadLimitsSettings | null> {
  const response = await fetchApi('/api/system/profile');
  const data = await response.json();
  if (!response.ok || !data?.workload) {
    return null;
  }
  return data.workload as WorkloadLimitsSettings;
}

export async function saveWorkloadLimits(
  payload: WorkloadLimitsPayload,
): Promise<WorkloadLimitsSettings | null> {
  const response = await fetchApi('/api/system/workload-limits', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data?.limits) {
    throw new Error(data?.error ?? 'Не удалось сохранить лимиты нагрузки');
  }
  return data as WorkloadLimitsSettings;
}

/** @deprecated use saveWorkloadLimits */
export async function setWorkloadSlider(slider: number): Promise<WorkloadLimitsSettings | null> {
  return saveWorkloadLimits({ slider });
}
