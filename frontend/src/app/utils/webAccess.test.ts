import { describe, expect, it } from 'vitest';
import { webAccessHint, type WebAccessMode } from './webAccess';

describe('webAccess', () => {
  it('explains each mode in Russian', () => {
    const modes: WebAccessMode[] = ['never', 'ask', 'always'];
    expect(webAccessHint(modes[0])).toMatch(/локальн/i);
    expect(webAccessHint(modes[1])).toMatch(/интернет/i);
    expect(webAccessHint(modes[2])).toMatch(/DuckDuckGo/i);
  });
});
