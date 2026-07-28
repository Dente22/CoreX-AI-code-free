---
description: Security and quality review of uncommitted changes. Check secrets, SQL injection, XSS, input validation.
---

# Security Review

Review uncommitted changes using `git diff --name-only HEAD`.

## Security (CRITICAL)

- Hardcoded credentials, API keys, tokens
- SQL injection (use parameterized queries only)
- XSS (sanitize user HTML)
- Missing input validation
- Insecure dependencies
- Path traversal risks

## Auth

- Authorization checks before sensitive operations
- Tokens in httpOnly cookies, not localStorage
- Rate limiting on API endpoints

## Output

Report with severity (CRITICAL, HIGH, MEDIUM, LOW), file:line, issue, suggested fix.

Block merge if any CRITICAL or HIGH security issue found.
