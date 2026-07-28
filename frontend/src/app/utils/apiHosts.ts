export function resolveApiHosts(
  primary: string | null,
  isElectron: boolean,
): string[] {
  if (primary && isElectron) {
    return [primary];
  }

  const fallbacks = ['http://127.0.0.1:8000', 'http://localhost:8000'];
  return primary ? [primary, ...fallbacks.filter((host) => host !== primary)] : fallbacks;
}
