export const NO_EXTENSION_ERROR =
  'Нельзя сохранить файл без расширения — одно название недостаточно. Укажите имя с расширением, например snake.py.';

export function filenameHasExtension(path: string): boolean {
  const name = (path || '').replace(/\\/g, '/').replace(/\/+$/, '').split('/').pop() ?? '';
  if (!name || name === '.' || name === '..') {
    return false;
  }
  if (name.startsWith('.') && name.length > 1) {
    return true;
  }
  const dot = name.lastIndexOf('.');
  if (dot <= 0) {
    return false;
  }
  return Boolean(name.slice(0, dot).trim() && name.slice(dot + 1).trim());
}
