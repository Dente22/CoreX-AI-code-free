# Web (HTML/CSS/JavaScript) Patterns

> This file provides reusable patterns for building web UI with plain HTML/CSS/JS or small SPA-style pages.

## UI Structure
- Use semantic HTML to express document structure.
- Split large pages into reusable components/partials (templates, modules, functions).

## Progressive Enhancement
- Render core content as static HTML first.
- Add client-side interactivity after initial render.

## State & Events
- Treat UI state as a single source of truth.
- Bind events once; prefer event delegation for lists.
- Keep handlers deterministic and side-effect free where possible.

## Responsive Design Contract
- Every layout must be tested at common breakpoints.
- Avoid “one viewport only” assumptions.

## Performance
- Avoid unnecessary DOM queries in hot paths.
- Defer non-critical JS; keep scripts small and focused.

