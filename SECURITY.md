# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in ModelMesh, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email: **security@apartsin.com**

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix or mitigation**: Within 30 days for critical issues

## Scope

The following are in scope:
- ModelMesh core library (Python and TypeScript)
- Docker proxy deployment
- Configuration parsing (YAML, programmatic)
- Secret store connectors
- Any code in this repository

The following are out of scope:
- Vulnerabilities in upstream dependencies (report to the dependency maintainer)
- Vulnerabilities in AI provider APIs (report to the provider)
- Social engineering attacks
- Denial of service via excessive API calls (rate limiting is the user's responsibility)

## Security Best Practices

When using ModelMesh:
- **Never commit API keys** — use environment variables or secret store connectors
- **Use `.env` files** only in development; use a proper secret manager in production
- **Pin dependency versions** in production deployments
- **Keep ModelMesh updated** to the latest supported version
- **Review YAML configs** before loading from untrusted sources

## Credit

We appreciate responsible disclosure and will credit reporters in release notes (unless you prefer to remain anonymous).
