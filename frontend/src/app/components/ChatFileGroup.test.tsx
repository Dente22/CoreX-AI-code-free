import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ChatFileGroup } from './ChatFileGroup';
import type { FileStatusEntry } from '../utils/chatFileStatus';

const files: FileStatusEntry[] = [
  { id: '1', action: 'записан', name: 'index.html', path: 'index.html', content: 'Файл записан: index.html' },
  { id: '2', action: 'записан', name: 'style.css', path: 'style.css', content: 'Файл записан: style.css' },
  { id: '3', action: 'записан', name: 'script.js', path: 'script.js', content: 'Файл записан: script.js' },
];

describe('ChatFileGroup', () => {
  it('collapses several files into one row', () => {
    const html = renderToStaticMarkup(<ChatFileGroup files={files} />);
    expect(html).toContain('3 файла');
    expect(html).toContain('index.html');
    expect(html).toContain('+2');
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain('script.js');
  });

  it('renders a single file as a compact row', () => {
    const html = renderToStaticMarkup(<ChatFileGroup files={[files[1]]} />);
    expect(html).toContain('1 файл');
    expect(html).toContain('style.css');
    expect(html).toContain('записан');
  });
});
