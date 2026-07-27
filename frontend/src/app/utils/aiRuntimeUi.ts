import type { AiMode } from './aiProvider';

export function resolveModeAfterChange(requestedMode: AiMode, responseMode?: AiMode): AiMode {
  return responseMode ?? requestedMode;
}

export function shouldApplyModeChange(
  currentMode: AiMode,
  nextMode: AiMode,
  disabled: boolean,
  busy: boolean,
): boolean {
  if (disabled || busy) {
    return false;
  }
  return currentMode !== nextMode;
}
