import { describe, expect, it } from 'vitest';
import { isOmniRouteProvider } from './aiProvider';

describe('isOmniRouteProvider', () => {
  it('detects the local gateway by port, host or name', () => {
    expect(
      isOmniRouteProvider({ base_url: 'http://127.0.0.1:20128/v1', name: 'Мой шлюз', api_type: 'openai' }),
    ).toBe(true);
    expect(
      isOmniRouteProvider({ base_url: 'https://omniroute.example.com/v1', name: 'X', api_type: 'openai' }),
    ).toBe(true);
    expect(
      isOmniRouteProvider({ base_url: 'http://10.0.0.5:9000/v1', name: 'OmniRoute', api_type: 'openai' }),
    ).toBe(true);
  });

  it('ignores other providers and Gemini', () => {
    expect(
      isOmniRouteProvider({ base_url: 'https://openrouter.ai/api/v1', name: 'OpenRouter', api_type: 'openai' }),
    ).toBe(false);
    expect(
      isOmniRouteProvider({ base_url: 'http://127.0.0.1:20128', name: 'G', api_type: 'gemini' }),
    ).toBe(false);
  });
});
