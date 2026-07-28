export function isInstallerForCoreX(fileName: string): boolean {
  return /^CoreX-Setup-[\d.]+(?:-[A-Za-z0-9.-]+)?\.exe$/i.test((fileName || '').trim());
}

export function extractVersionFromInstallerName(fileName: string): string {
  const match = /^CoreX-Setup-([0-9]+\.[0-9]+\.[0-9]+)(?:-[A-Za-z0-9.-]+)?\.exe$/i.exec(
    (fileName || '').trim(),
  );
  return match?.[1] ?? '';
}
