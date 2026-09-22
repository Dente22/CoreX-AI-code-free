import { fetchApi } from './api';

export interface GpuOption {
  id: string;
  name: string;
  label?: string;
  kind: 'nvidia' | 'intel' | 'other' | 'cpu' | string;
  vram_gb: number | null;
  recommended: boolean;
  selected: boolean;
}

export interface GpuPreferenceSnapshot {
  gpus: GpuOption[];
  gpu_id: string;
  gpu_name: string;
  gpu_choice_needed: boolean;
  ollama_restarted?: boolean;
  ollama_using_desktop?: boolean;
  success?: boolean;
  error?: string;
}

export function gpuButtonLabel(gpu: GpuOption): string {
  const base = (gpu.label || gpu.name || gpu.id).trim();
  const rec = gpu.recommended ? ' · рек.' : '';
  return `${base}${rec}`;
}

export async function saveGpuPreference(gpuId: string): Promise<GpuPreferenceSnapshot> {
  const response = await fetchApi('/api/system/gpu-preference', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gpu_id: gpuId }),
  });
  const data = await response.json();
  if (!response.ok || data?.success === false) {
    throw new Error(data?.error || 'Не удалось сохранить графический процессор');
  }
  return data as GpuPreferenceSnapshot;
}
