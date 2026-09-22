import { describe, expect, it } from 'vitest';
import { gpuButtonLabel, type GpuOption } from './gpuPreference';

function gpu(partial: Partial<GpuOption>): GpuOption {
  return {
    id: 'nvidia:0',
    name: 'NVIDIA T600',
    label: 'T600',
    kind: 'nvidia',
    vram_gb: 4,
    recommended: false,
    selected: false,
    ...partial,
  };
}

describe('gpuPreference', () => {
  it('marks the recommended GPU in the button label', () => {
    expect(gpuButtonLabel(gpu({ recommended: true }))).toBe('T600 · рек.');
    expect(gpuButtonLabel(gpu({ recommended: false, label: 'UHD Graphics 630' }))).toBe(
      'UHD Graphics 630',
    );
  });
});
