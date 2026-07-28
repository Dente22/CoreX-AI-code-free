# Web (HTML/CSS/JavaScript) Security

> Web rules extend the project-wide `common/security.md`.

## XSS Prevention (CRITICAL)
- Never render untrusted HTML from strings.
- If you must display markup, sanitize it on a server side with a strict allow-list.
- Prefer `textContent` over `innerHTML`.

## Client-Side Hardening
- Validate all input on the server (never trust frontend-only checks).
- Use CSRF protection for state-changing requests.
- Avoid exposing stack traces and internal errors to the client.

## Content Security Policy (CSP)
- Use CSP to restrict `script-src` and reduce impact of injection.
- Avoid inline scripts where possible; use hashes/nonces.

