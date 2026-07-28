export const COREX_LOGO_SVG = `${import.meta.env.BASE_URL}corex-logo.svg`;
export const COREX_LOGO_PNG = `${import.meta.env.BASE_URL}corex-icon.png`;
/** SVG всегда в public/ — безопасный дефолт без 404. */
export const COREX_LOGO_DEFAULT = COREX_LOGO_SVG;

/**
 * Следующий src при ошибке загрузки. Не зацикливается: png → svg → скрыть.
 */
export function nextLogoSrcOnError(currentSrc: string): string | null {
  if (currentSrc.includes('corex-icon.png')) {
    return COREX_LOGO_SVG;
  }
  return null;
}
