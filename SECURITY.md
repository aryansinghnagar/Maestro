# Maestro Security Policy

**Last updated: 2026-07-09**

## Supported Versions

| Version | Supported |
|---|---|
| 0.2.x | ✅ |
| 0.1.x | ⚠️ (security fixes only) |
| < 0.1 | ❌ |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email `security@aryansinghnagar.dev`. Please include:

1. Description of the vulnerability
2. Steps to reproduce
3. Affected versions
4. Potential impact
5. Suggested fix (optional)

### PGP encryption (optional)

For sensitive reports, encrypt with our PGP key:

```
-----BEGIN PGP PUBLIC KEY BLOCK-----
[KEY BLOCK HERE — generate and add]
-----END PGP PUBLIC KEY BLOCK-----
```

Fingerprint: `[ADD FINGERPRINT]`

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

- **Broker socket:** `SO_PEERCRED` (Linux) / `getpeereid` (macOS) / named pipe ACL (Windows)
- **REST API:** Random token generated on first run, stored with `chmod 0600`
- **WebSocket:** Origin header validation
- **Update channel:** TUF with threshold=3 of 5 keys

### Sandboxing

- **Untrusted plugins:** WASM runtime (wasmtime), no file/network/process access
- **Trusted plugins:** In-process, RestrictedPython defense-in-depth
- **Config:** JSON schema validation, AST sandbox for expressions

### Audit log

All OS input injections are logged to `audit.log` with:
- Timestamp
- Gesture name
- Action performed
- Target app (foreground app name)

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
- [ ] Config signing (planned for v0.3)
- [ ] Sigstore-signed releases (planned for v0.2)
- [ ] SBOM generation (planned for v0.2)
- [ ] eBPF input filter on Linux (planned for v0.3)

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
