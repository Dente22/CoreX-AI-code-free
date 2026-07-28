import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkModeSelector } from './WorkModeSelector';

describe('WorkModeSelector', () => {
  it('uses compact button layout (no flex-1)', () => {
    const html = renderToStaticMarkup(
      <WorkModeSelector
        workMode="single"
        onWorkModeChange={() => {
          // noop
        }}
      />,
    );

    expect(html).not.toContain('flex-1');
    expect(html).toContain('flex-none');
  });
});

