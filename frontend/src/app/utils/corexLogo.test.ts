import { describe, expect, it } from 'vitest';
import {
  COREX_LOGO_DEFAULT,
  COREX_LOGO_PNG,
  COREX_LOGO_SVG,
  nextLogoSrcOnError,
} from './corexLogo';

describe('corexLogo', () => {
  it('defaults to svg shipped in public/', () => {
    expect(COREX_LOGO_DEFAULT).toBe(COREX_LOGO_SVG);
    expect(COREX_LOGO_SVG).toMatch(/corex-logo\.svg$/);
  });

  it('falls back from png to svg once', () => {
    expect(nextLogoSrcOnError(COREX_LOGO_PNG)).toBe(COREX_LOGO_SVG);
  });

  it('does not loop after svg fails', () => {
    expect(nextLogoSrcOnError(COREX_LOGO_SVG)).toBeNull();
  });
});
