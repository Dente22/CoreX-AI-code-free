import { describe, expect, it } from 'vitest';
import { resolveModeAfterChange, shouldApplyModeChange } from './aiRuntimeUi';

describe('aiRuntimeUi', () => {
  it('keeps requested online mode when backend omits mode in response', () => {
    expect(resolveModeAfterChange('online')).toBe('online');
  });

  it('uses backend mode when provided', () => {
    expect(resolveModeAfterChange('online', 'local')).toBe('local');
  });

  it('blocks mode change while busy or disabled', () => {
    expect(shouldApplyModeChange('local', 'online', false, true)).toBe(false);
    expect(shouldApplyModeChange('local', 'online', true, false)).toBe(false);
  });

  it('allows mode change when idle', () => {
    expect(shouldApplyModeChange('local', 'online', false, false)).toBe(true);
    expect(shouldApplyModeChange('online', 'online', false, false)).toBe(false);
  });
});
