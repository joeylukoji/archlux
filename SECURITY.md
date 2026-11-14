# Security policy

## Supported versions

Only the latest release, and `main`, receive security fixes before 1.0.0.

## What counts as a vulnerability

archlux reads files it did not write: JSON plans, DXF and IFC drawings. A crash is a
bug; a vulnerability is a file that makes archlux execute code, read or write outside the
paths it was given, exhaust memory or CPU without bound, or produce a certificate that
says "valid" for an invalid plan. The last one matters as much as the others: the
geometric certificate is the product.

## Reporting

Do **not** open a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/joeylukoji/archlux/security/advisories/new)
with a minimal file that reproduces the problem, the archlux version and the command.
You will get an answer within 14 days. Fixes are released as a patch version and credited
in `CHANGELOG.md` unless you ask otherwise.
