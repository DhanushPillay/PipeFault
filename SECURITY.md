# Security policy

## Supported versions

Only the latest commit on `main` is supported.

## Reporting a vulnerability

Please open a private security advisory on GitHub or email the maintainer. Do not file public issues for suspected vulnerabilities.

## Data and secrets

- No credentials are stored in the repository.
- Downloads use public URLs only. No dataset requires account credentials.
- Raw data and artifacts are gitignored.
- CI runs gitleaks and pip-audit on every pull request.
