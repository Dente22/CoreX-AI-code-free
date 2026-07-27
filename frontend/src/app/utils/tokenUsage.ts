import { fetchApi } from './api';

export interface TokenUsageLimits {
  enabled: boolean;
  session_limit: number;
  daily_limit: number;
  warn_at_percent: number;
}

export interface TokenUsageSummary {
  limits: TokenUsageLimits;
  session: { total_tokens: number; requests: number };
  daily: { total_tokens: number; requests: number };
  remaining_session: number;
  remaining_daily: number;
  session_percent: number;
  daily_percent: number;
}

export async function fetchTokenUsage(): Promise<TokenUsageSummary | null> {
  const response = await fetchApi('/api/ai/usage');
  if (!response.ok) return null;
  const data = await response.json();
  if (!data?.success) return null;
  return data as TokenUsageSummary;
}

export async function updateTokenLimits(
  limits: Partial<TokenUsageLimits>,
): Promise<{ success?: boolean; error?: string }> {
  const response = await fetchApi('/api/ai/usage/limits', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(limits),
  });
  const data = await response.json();
  if (!response.ok || data?.error) {
    return { error: data?.error || 'Не удалось сохранить лимиты' };
  }
  return { success: true };
}

export async function resetSessionTokenUsage(): Promise<void> {
  await fetchApi('/api/ai/usage/reset', { method: 'POST' });
}
