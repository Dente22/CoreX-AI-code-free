import { describe, expect, it } from 'vitest';
import {
  getDefaultOnlineProviderTemplate,
  getFreeBaseOnlineProviderTemplate,
  getProviderTemplateById,
  ONLINE_PROVIDER_TEMPLATES,
} from './onlineProviderTemplates';

describe('online provider templates', () => {
  it('returns OpenAI template with OpenAI-compatible api type', () => {
    const template = getProviderTemplateById('openai');
    expect(template).toBeDefined();
    expect(template?.apiType).toBe('openai');
    expect(template?.defaultBaseUrl).toBe('https://api.openai.com/v1');
  });

  it('returns Gemini template with native gemini api type', () => {
    const template = getProviderTemplateById('gemini');
    expect(template).toBeDefined();
    expect(template?.apiType).toBe('gemini');
    expect(template?.defaultBaseUrl).toBe('https://generativelanguage.googleapis.com/v1beta');
    expect(template?.defaultModel).toBe('gemini-2.5-flash');
  });

  it('contains multiple supported providers for AI selection', () => {
    expect(ONLINE_PROVIDER_TEMPLATES.length).toBeGreaterThanOrEqual(5);
    const ids = ONLINE_PROVIDER_TEMPLATES.map((item) => item.id);
    expect(ids).toContain('openai');
    expect(ids).toContain('groq');
    expect(ids).toContain('together');
    expect(ids).toContain('openrouter');
    expect(ids).toContain('openrouter-free');
    expect(ids).toContain('gemini');
  });

  it('uses OpenRouter Free as the default base provider with setup guide', () => {
    const freeBase = getFreeBaseOnlineProviderTemplate();
    const defaultTemplate = getDefaultOnlineProviderTemplate();

    expect(freeBase?.id).toBe('openrouter-free');
    expect(defaultTemplate.id).toBe('openrouter-free');
    expect(freeBase?.isFreeBase).toBe(true);
    expect(freeBase?.defaultBaseUrl).toBe('https://openrouter.ai/api/v1');
    expect(
      freeBase?.defaultModel === 'openrouter/free' || freeBase?.defaultModel.endsWith(':free'),
    ).toBe(true);
    expect(freeBase?.guide?.steps.length).toBeGreaterThanOrEqual(3);
    expect(freeBase?.guide?.steps.some((step) => step.url?.includes('openrouter.ai/keys'))).toBe(
      true,
    );
  });
});
