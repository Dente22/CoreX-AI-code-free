import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { getRequiredLibraryResources } = require('./installerLibraryConfig.cjs');

const FRONTEND_ROOT = path.dirname(fileURLToPath(import.meta.url));

describe('installerLibraryConfig', () => {
  it('package.json extraResources includes agents, skills, knowledge', () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(FRONTEND_ROOT, '..', 'package.json'), 'utf8'),
    ) as { build?: { extraResources?: Array<{ from: string; to: string }> } };
    const extra = pkg.build?.extraResources ?? [];
    for (const required of getRequiredLibraryResources()) {
      expect(
        extra.some((item) => item.from === required.from && item.to === required.to),
      ).toBe(true);
    }
  });
});
