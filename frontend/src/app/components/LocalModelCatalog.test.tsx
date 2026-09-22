import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { LocalModelCatalog } from './LocalModelCatalog';
import { FALLBACK_AI_PROVIDERS } from '../utils/aiProvider';

describe('LocalModelCatalog', () => {
  it('renders hardware tabs and download actions compactly', () => {
    const html = renderToStaticMarkup(
      <LocalModelCatalog
        providers={FALLBACK_AI_PROVIDERS}
        selectedId="ollama-qwen"
        recommendedId="ollama-qwen"
        vramGb={4}
        ramGb={16}
        installedById={{ 'ollama-qwen': true }}
        needsImportById={{}}
        busyId=""
        pullProgress={null}
        savingId={null}
        onSelect={() => {}}
        onPull={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(html).toContain('Слабый ПК');
    expect(html).toContain('Средний ПК');
    expect(html).toContain('Мощный ПК');
    expect(html).toContain('Qwen 3B');
    expect(html).toContain('Скачать');
    expect(html).not.toContain('select');
  });

  it('explains auto-switch when both weak-PC models are installed', () => {
    const html = renderToStaticMarkup(
      <LocalModelCatalog
        providers={FALLBACK_AI_PROVIDERS}
        selectedId="ollama-qwen"
        recommendedId="ollama-qwen"
        vramGb={4}
        ramGb={16}
        installedById={{ 'ollama-qwen': true, 'ollama-lite': true }}
        needsImportById={{}}
        busyId=""
        pullProgress={null}
        savingId={null}
        onSelect={() => {}}
        onPull={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(html).toContain('Автосмена');
    expect(html).toContain('Phi-3 Mini');
  });
});
