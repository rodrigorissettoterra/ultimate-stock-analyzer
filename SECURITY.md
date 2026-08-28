# Security Policy

## Public-by-design rule

This repository must never contain real API keys, tokens, passwords, cookies, database credentials, private certificates, personal data, brokerage credentials, paid/licensed datasets, or production database dumps.

Use environment variables and `.env.example`. Local `.env` files and data lake paths are ignored by Git.

## If a secret is committed

1. Treat the secret as compromised immediately.
2. Revoke/rotate it at the provider.
3. Remove it from the repository and, when necessary, rewrite Git history.
4. Document the incident without reproducing the secret.

## Reporting vulnerabilities

Please report security issues privately to the repository owner rather than opening a public issue containing exploit details or secrets.
