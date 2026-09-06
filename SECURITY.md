# Maestro Security Policy

**Last updated: 2026-09-04**

## Supported Versions

| Version | Supported |
|---|---|
| 1.3.x | ✅ (Active) |
| 1.2.x | ⚠️ (Security fixes only) |
| 1.1.x | ❌ (End of life — upgrade to 1.3.x) |
| < 1.1 | ❌ |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email `security@aryansinghnagar.dev` or report via [GitHub Security Advisories](https://github.com/aryansinghnagar/Maestro/security/advisories/new). Please include:

1. Description of the vulnerability
2. Steps to reproduce
3. Affected versions and operating systems
4. Potential impact
5. Suggested remediation (optional)

### Response timeline

| Event | Target |
|---|---|
| Acknowledge receipt | < 24 hours |
| Initial assessment | < 72 hours |
| Fix or workaround | < 7 days (critical), < 30 days (high), < 90 days (medium) |
| Public disclosure | After fix released, or 90 days (whichever is first) |

### Disclosure policy

- We follow [Project Zero's disclosure policy](https://googleprojectzero.blogspot.com/p/vulnerability-disclosure-faq.html).
- We will credit reporters in the release notes (unless they prefer to remain anonymous).
- We do NOT offer monetary rewards at this time (no bug bounty program).

## Security Architecture

### Threat model

See [docs/specs/ds-007-threat-model.md](docs/specs/ds-007-threat-model.md) for the full STRIDE threat model.

### Security boundaries

1. **Camera process** — separate process, reads camera, writes to SHM (chmod 0600)
2. **Engine process** — reads SHM, runs inference, emits gesture events
3. **Broker process** — receives IPC from engine, performs OS input injection
4. **Plugin runtime** — WASM sandbox (untrusted) or in-process (trusted)

### Authentication

- **Broker socket:** `SO_PEERCRED` (Linux) / `getpeereid` (macOS) / named-pipe SID check (Windows). The Windows path now **fail-closes** on any exception during the SID lookup — previously it failed open (audit fix MAE-SEC-001).
- **REST API:** Random token generated on first run, stored with `chmod 0600`. The CLI now sends the token via the `Authorization: Bearer` header instead of a URL query parameter (audit fix MAE-SEC-005). Query-parameter tokens are deprecated and emit a server-side warning.
- **WebSocket:** Origin header validation. The `"null"` Origin is no longer accepted — only explicit `localhost` / `127.0.0.1` origins are allowed (audit fix MAE-SEC-004).
- **Update channel:** TUF with threshold=3 of 5 keys. The placeholder `BOOTSTRAP_ROOT` is now disabled by default and emits a warning when used (audit fix MAE-SEC-002). Auto-update is effectively disabled until a real TUF repository with real Ed25519 keys is published.

### Sandboxing

- **Untrusted plugins:** WASM runtime (wasmtime), no file/network/process access
- **Trusted plugins:** In-process, RestrictedPython defense-in-depth
- **Config:** JSON schema validation, AST sandbox for expressions
- **Archive extraction:** The `apply_update` function now validates every member's resolved path against the extraction directory before extraction, blocking zip-slip / path-traversal attacks (audit fix MAE-SEC-008).
- **AppleScript bridge:** The `run_applescript` bridge now caps script length at 8 KiB, rejects scripts containing `do shell script` or `POSIX path of` patterns, and passes `-l AppleScript` explicitly to prevent JavaScript-mode escapes (audit fix MAE-SEC-006).
- **Vosk model download:** The CLI verifies the SHA-256 of the downloaded Vosk model zip against a pinned hash before extraction (audit fix MAE-SEC-017). The hash is currently empty pending maintainer rotation; the production command refuses to extract until the hash is set.

### Audit log

All OS input injections are logged to `audit.log` with:
- Timestamp
- Gesture name
- Action performed
- Target app (foreground app name)
- Authentication rejections (audit fix MAE-SEC-001: Windows verification failures now log at ERROR level)

## Security Hardening Checklist

- [x] No hardcoded secrets (random token generation)
- [x] Broker socket authentication
- [x] TUF threshold=3
- [x] Voice listener offline (Vosk)
- [x] Plugin WASM sandbox
- [x] AST sandbox bypass fix (block `from X import Y`)
- [x] Subprocess timeouts
- [x] WebSocket CSWSH fix (Origin validation)
- [x] SHM chmod 0600
- [x] Audit log
- [x] SBOM generation (CycloneDX v1.5 format in packaging/sbom.cdx.json)
- [ ] Sigstore-signed releases (OIDC release pipeline)
- [ ] Config signing (planned for v2.0)

## Known Security Considerations

### Local attack surface

Maestro runs as your user. Any process running as your user can:
- Connect to the broker socket (if it can guess the path) — mitigated by `SO_PEERCRED`
- Read the audit log — by design (it's your data)
- Read the config file — by design (it's your data)
- Read the SHM segment — mitigated by `chmod 0600`

### Network attack surface

By default, Maestro has NO network attack surface:
- REST API binds to `127.0.0.1:8765` (not `0.0.0.0`)
- WebSocket binds to `127.0.0.1:8765`
- No outbound network calls (Vosk is offline)
- Update channel is opt-in and TUF-verified

If you enable remote access (bind to `0.0.0.0`), you assume the risk.

### Hardware attack surface

- **Camera:** Any app with camera permission can read the same camera stream. Maestro cannot prevent this.
- **Microphone:** Same as camera.
- **Input devices:** Any app in the `input` group (Linux) can inject keystrokes. Maestro does not change this.

## Incident Response

See [docs/specs/ds-007-threat-model.md#incident-response](docs/specs/ds-007-threat-model.md) for the incident response playbook.

## Security Update Process

1. Vulnerability reported
2. Maintainer triages within 72 hours
3. Fix developed on private branch
4. CVE requested (if applicable)
5. Fix released as `patch` version
6. Public disclosure after release
7. Blog postmortem published

## Contact

- Security email: `security@aryansinghnagar.dev`
- General issues: [GitHub Issues](https://github.com/aryansinghnagar/Maestro/issues)
