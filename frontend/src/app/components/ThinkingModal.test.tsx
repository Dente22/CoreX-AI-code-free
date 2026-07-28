import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ThinkingMessage } from './ThinkingModal';

describe('ThinkingMessage', () => {
  it('renders compact collapsed thinking row without expanding all thoughts', () => {
    const html = renderToStaticMarkup(
      <ThinkingMessage thoughts={['Читаю файл', 'Пишу анимацию', 'Проверяю результат']} />,
    );

    expect(html).toContain('Думает');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('3 шаг');
    expect(html).not.toContain('max-h-40');
    expect(html).not.toContain('Читаю файл');
    expect(html).not.toContain('Пишу анимацию');
  });

  it('shows collapsed loader even when thoughts are empty', () => {
    const html = renderToStaticMarkup(<ThinkingMessage thoughts={[]} isThinking />);
    expect(html).toContain('Думает');
    expect(html).toContain('ожидание ответа');
    expect(html).not.toContain('max-h-40');
  });

  it('returns null when idle and no thoughts', () => {
    const html = renderToStaticMarkup(<ThinkingMessage thoughts={[]} isThinking={false} />);
    expect(html).toBe('');
  });
});
