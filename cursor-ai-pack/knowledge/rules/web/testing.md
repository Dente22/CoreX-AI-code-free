# Web (HTML/CSS/JavaScript) Testing

> Web rules extend the project-wide `common/testing.md`.

## Unit Tests
- Test pure JS functions (formatters, validators, parsers) in isolation.
- Avoid DOM in unit tests; use DOM in integration/E2E.

## DOM / Integration Tests
- Use a headless browser runner for DOM behavior.
- Verify accessibility basics (keyboard navigation, focus order).

## E2E Tests (CRITICAL)
- Use Playwright for critical user flows.
- Validate that generated UI works at multiple viewport sizes.

## CSS Regression
- Keep CSS predictable: avoid magic numbers; prefer design tokens/variables.
- For critical layouts, use screenshot diffs (if feasible).

