# Web (HTML/CSS/JavaScript) Coding Style

> Web rules extend the project-wide `common` guidelines.

## Semantic HTML (CRITICAL)
- Use correct tag names (`header`, `nav`, `main`, `section`, `button`, `form`, `label`).
- Every interactive element must be reachable by keyboard and have an accessible name (`aria-label`, visible text, `title` only when needed).

## Accessibility First
- Prefer native controls over custom clickable `div`s.
- Keep color contrast readable.
- Respect `prefers-reduced-motion` for animations.

## CSS Rules
- Prefer CSS custom properties (variables) for theme values.
- Keep styles scoped (use BEM-like class names or component containers).
- Responsive layout must use flexible units (`rem`, `%`, `clamp()`), not fixed pixel-only widths.

## DOM Safety / Client JS
- Never inject untrusted HTML with `innerHTML` unless you strictly sanitize it.
- Prefer `textContent` for user-provided strings.
- Keep event handlers small; move logic to functions/modules.

