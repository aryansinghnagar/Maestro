---
title: "RFC-010: Plugin Marketplace Governance"
---

### RFC-010: Plugin Marketplace Governance

**Author:** Refactor Team
**Date:** 2026-07-09
**Status:** Draft (v0.3+)

#### Problem
A community plugin marketplace needs governance: who can publish, how are plugins reviewed, how are malicious plugins removed.

#### Proposed Solution

- Anyone can publish plugins to PyPI with `maestro-*` prefix
- Maestro CLI lists plugins from curated `marketplace.json` (review required)
- Review process: static analysis, manifest validation, license check, permissions review, manual review
- Plugins signed with Sigstore (keyless, OIDC)
- Malicious plugin removal: yank from PyPI, remove from marketplace.json, notify users via in-app alert

#### Review Process

1. **Automated checks (always):**
   - AST scan (no forbidden imports/calls)
   - Manifest validation
   - License compatibility check
   - Permissions minimality check

2. **Manual review (for marketplace listing):**
   - Maintainer reads code for safety
   - Tests plugin in sandboxed environment
   - Verifies claims in manifest
   - Signs off on review

3. **Continuous monitoring:**
   - Re-scan on each version bump
   - User reports trigger re-review
   - Critical issues → immediate delisting

#### Removal Process

1. Yank from PyPI (prevents new installs)
2. Remove from `marketplace.json`
3. Notify users via in-app alert
4. Blog post explaining removal
5. CVE if security issue

#### Defer to v0.3+
Marketplace is not blocking for v0.2. Implement basic `maestro plugins install <pypi-name>` for v0.2, formal marketplace for v0.3.

---