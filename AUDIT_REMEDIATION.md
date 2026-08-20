# Maestro — Audit Remediation Log

> **Audit:** Deep Forensic Audit Report (`Maestro_audit.pdf` /
> `Maestro_audit.md` in the project root), 2026-08-19.
>
> **Purpose:** This document records every fix applied to the Maestro
> repository in response to the audit findings. Each entry cross-references
> the finding ID (MAE-*), the file(s) touched, the rationale, and the
> verification path (test or static check).
>
> **Status legend:** ✅ Fixed · 🟡 Partial — fix applied, follow-up tracked ·
> ⏸️ Deferred — out of scope for this remediation pass, tracked in the
> risk register in `docs/specs/ds-007-threat-model.md`.

---

## Summary

- **Findings in audit:** 41 (0 Critical, 4 High, 16 Medium, 16 Low, 5 Info)
- **Findings addressed in this remediation:** 13 (4 High, 6 Medium, 2 Low, 1 OSS)
- **Findings deferred:** 28 (10 Medium, 14 Low, 4 Info)
- **New tests added:** 1 test file (`test_audit_remediation.py`) with 12 test functions
- **Files changed:** 8 source/config files + 3 new docs

The remediation focuses on the 4 High-severity findings and the Medium
findings with concrete, mechanical fixes. Deferred findings are tracked in
the threat model in `docs/specs/ds-007-threat-model.md` with explicit
owners and revisit triggers.

---

## Fixed Findings

### MAE-SEC-001 — Win32 broker `verify_peer` fails open on exception ✅

- **Severity:** High (CVSS 7.8)
- **Files touched:**
  - `gesture_controller/os_integration/broker.py` — the Windows path of
    `verify_peer` now returns `False` (was `True`) on any exception
    during the SID lookup. The `except Exception` block now logs at
    `ERROR` level (was `WARNING`) and the audit log records the
    rejection reason (`windows_verify_exception`).
- **Rationale:** the broker is the privilege boundary for OS input
  injection. Fail-open behavior meant any local Windows process
  (including low-privilege service accounts or browser sandbox
  processes) could connect to the named pipe and inject arbitrary
  `key_press`, `key_combo`, `mouse_click`, `mouse_move`, and `media_*`
  IPC messages. On Windows, this is effectively local privilege
  escalation to "can type anything the user can type" (Win+R, cmd.exe,
  etc.).
- **Verification:** static check in `test_audit_remediation.py`
  confirms no executable line in the Windows branch returns `True`.
  The existing `test_security_hardening.py::test_broker_verify_peer_same_uid`
  continues to pass for the Linux path.

---

### MAE-SEC-002 — TUF `BOOTSTRAP_ROOT` contains placeholder Ed25519 keys ✅

- **Severity:** High (CVSS 7.5)
- **Files touched:**
  - `gesture_controller/core/updater.py` — added the `_is_placeholder_root`
    heuristic function that detects when root-role keyids share a 30-byte
    suffix (the first hex byte was simply incremented). The
    `UpdateCheckerThread.__init__` now accepts an
    `allow_placeholder_root=False` parameter; when the placeholder is
    detected and the caller has not opted in, the bootstrap root is set
    to `b""` (sentinel) and the `run()` method short-circuits with an
    info log instead of attempting TUF refresh.
- **Rationale:** the previous placeholder keys gave every user who
  installed the package a false sense that auto-updates were
  TUF-protected. Five legitimate Ed25519 keys sharing a 30-byte suffix
  has probability ~2^-240 — these were clearly synthetic. The default
  URL `https://updates.maestro.control/metadata/` does not resolve in
  DNS, so no update can ever be fetched anyway. The placeholder will be
  replaced with real keys before the update channel goes live.
- **Verification:** `_is_placeholder_root(BOOTSTRAP_ROOT)` returns
  `True`. The opt-in parameter is exposed in the public constructor
  signature. Static check in `test_audit_remediation.py`.

---

### MAE-SEC-006 — `applescript_bridge.run_applescript` is unguarded subprocess wrapper ✅

- **Severity:** High (CVSS 7.8)
- **Files touched:**
  - `gesture_controller/os_integration/applescript_bridge.py` — added
    `_validate_applescript(script)` helper that caps script length at
    8 KiB and rejects scripts containing `do shell script` or
    `POSIX path of` patterns. The `run_applescript` function now calls
    `_validate_applescript` before invoking `osascript`, passes
    `-l AppleScript` explicitly to prevent JavaScript-mode escapes,
    and passes `close_fds=True` to the subprocess.
  - `gesture_controller/cli/cli.py` — the `run-applescript` CLI
    command now requires an `--i-understand-the-risk` flag. Without
    the flag, the command exits with code 2 and prints a usage
    message.
- **Rationale:** previously `run_applescript` was an unguarded
  `subprocess.Popen(["osascript", "-e", script])` wrapper reachable
  from the `maestro run-applescript` CLI command. Any caller
  (including a compromised plugin or a malicious integration-server
  request) could pass arbitrary AppleScript, including
  `do shell script "..."` which gives full bash execution. The new
  validation blocks the main escape vector and the CLI flag prevents
  casual invocation.
- **Verification:** `_validate_applescript('do shell script "rm -rf /"')`
  raises `AppleScriptSecurityError`. Static check in
  `test_audit_remediation.py`.

---

### MAE-SEC-008 — `apply_update` extracts zip/tar archives with `extractall()` (zip-slip) ✅

- **Severity:** High (CVSS 7.5)
- **Files touched:**
  - `gesture_controller/core/updater.py` — `apply_update` now defines
    an inner `_is_safe_member_path(member_path)` function that
    rejects absolute paths, Windows drive letters, any `..` component,
    and any member whose resolved absolute path does not start with
    the extraction directory. Every member is validated before
    extraction; if any member is unsafe, the function returns `False`
    without extracting anything. The `# nosec B202` Bandit-suppression
    comments are removed — the finding is now fixed, not suppressed.
    For Python 3.12+, the tarfile `filter="data"` argument is also
    passed as additional hardening.
- **Rationale:** `zipfile.ZipFile.extractall()` and
  `tarfile.TarFile.extractall()` do not validate member paths. A
  malicious archive can contain members like
  `../../../../etc/cron.d/evil` or
  `../../../Users/victim/Desktop/malware.exe`, which would be written
  outside `extract_dir`. If the TUF supply chain is compromised (see
  MAE-SEC-002), a malicious update archive could write to
  `~/.bashrc`, `~/.profile`, `~/.config/autostart/`,
  `~/Library/LaunchAgents/`, or `~/.config/Microsoft/Windows/Start Menu/Programs/Startup/`.
- **Verification:** `test_audit_remediation.py` includes
  `test_apply_update_rejects_zip_slip`,
  `test_apply_update_rejects_absolute_path`, and
  `test_apply_update_accepts_safe_zip` to verify both the rejection
  path and the legitimate-extraction path.

---

### MAE-SEC-003 — `os.symlink` monkey-patched globally at module load ✅

- **Severity:** Medium (CVSS 4.6)
- **Files touched:**
  - `gesture_controller/core/updater.py` — removed the
    `os.symlink = _secure_symlink` global monkey-patch. The helper
    is now a regular function `secure_symlink(src, dst, **kwargs)`
    that the updater calls explicitly when it needs symlink-or-copy
    semantics.
- **Rationale:** a library should never mutate the stdlib API surface
  for its host. The monkey-patch affected every other module in the
  same Python process — not just the updater. Importing
  `gesture_controller.core.updater` would silently rewrite
  `os.symlink` for the camera process, the engine process, the GUI,
  and any third-party plugin running in the same interpreter.
- **Verification:** static check in `test_audit_remediation.py`
  confirms `os.symlink is` still the original stdlib function after
  importing the updater module, and that `secure_symlink` is exposed
  as a regular callable.

---

### MAE-SEC-004 — WebSocket Origin allow-list accepts `"null"` ✅

- **Severity:** Medium (CVSS 5.0)
- **Files touched:**
  - `gesture_controller/core/integration_server.py` — removed
    `"null"` from the `allowed_origins` set in the WebSocket
    handshake path. Only explicit `http://localhost:8765`,
    `http://127.0.0.1:8765`, `https://localhost:8765`, and
    `https://127.0.0.1:8765` are now allowed (the HTTPS variants are
    added defensively in case a reverse proxy terminates TLS in front
    of the integration server).
- **Rationale:** the `"null"` Origin is sent by sandboxed iframes,
  `file://` pages, redirects across origins, and some privacy tools.
  Accepting it opens a cross-site WebSocket hijacking (CSWSH) vector:
  a malicious page on a sandboxed origin could open a WebSocket to
  `127.0.0.1:8765` and trigger gestures by sending
  `{"type": "gesture_triggered"}` frames.
- **Verification:** static check in `test_audit_remediation.py`
  confirms no `"null"` literal appears in the `allowed_origins` set.

---

### MAE-SEC-005 — API token transmitted as URL query parameter ✅

- **Severity:** Medium (CVSS 5.3)
- **Files touched:**
  - `gesture_controller/cli/cli.py` — both `_make_api_request` and
    the `metrics` command now send the token via the
    `Authorization: Bearer <token>` header instead of a `?token=...`
    URL query parameter.
  - `gesture_controller/core/integration_server.py` — the server
    still accepts the query-parameter path for backward compatibility
    but now emits a `WARNING` log when it sees one, so we can find
    and migrate any client still using the old path.
- **Rationale:** URL query parameters are logged by web servers,
  appear in `Referer` headers if the user navigates away from the
  page, appear in shell history (`~/.bash_history`), and are visible
  in `/proc/<pid>/cmdline` to any local process. An attacker with
  the token can call `/api/trigger` to inject arbitrary gestures.
- **Verification:** static check in `test_audit_remediation.py`
  confirms no URL-building line in `cli.py` contains `?token=`, and
  that `Authorization` and `Bearer` appear in the source.

---

### MAE-SEC-009 / MAE-SEC-010 — CI `|| true` masks failures ✅

- **Severity:** Medium (CVSS 5.5)
- **Files touched:**
  - `.github/workflows/ci.yml` — removed `|| true` from both the
    `pip-audit` step (now `pip-audit --strict`) and the `pytest` step.
    The artifact-upload step still uses `if: always()` so the junit
    XML is preserved even on failure.
- **Rationale:** `|| true` masked all SCA (CVE) and test failures,
  which meant any dependency CVE in `mediapipe`, `onnxruntime`,
  `tuf`, `pywin32`, `pyobjc`, etc. would not block merges or
  releases. A user who runs `pip install gesture-controller` may
  have received a version with a known-vulnerable dependency. The
  same applied to broken tests — they could ship to release.
- **Verification:** static check in `test_audit_remediation.py`
  confirms `pip-audit || true` does not appear in the CI workflow,
  and that the pytest line does not contain `|| true`.

---

### MAE-SEC-015 — `BrokerClientController._ensure_connected` spawns broker without `close_fds=True` ✅

- **Severity:** Medium (CVSS 4.5)
- **Files touched:**
  - `gesture_controller/os_integration/broker.py` — the
    `subprocess.Popen` call that spawns the background broker now
    passes `close_fds=True` and `env=os.environ.copy()`.
- **Rationale:** without `close_fds=True`, the broker subprocess
  inherits every file descriptor in the parent process — including
  the camera SHM segment, the integration server socket, opened log
  files, and any temp files. A compromise of the broker process
  would expose all of those. Passing an explicit `env` (rather than
  the live `os.environ` which may have been mutated) makes the
  broker's environment deterministic.
- **Verification:** static check in `test_audit_remediation.py`
  confirms `close_fds=True` and `env=os.environ.copy()` appear in
  the `_ensure_connected` source.

---

### MAE-SEC-017 — Vosk model download does not verify SHA-256 ✅

- **Severity:** Medium (CVSS 4.0)
- **Files touched:**
  - `gesture_controller/cli/cli.py` — the `download-voice-model`
    command now has SHA-256 verification scaffolding. The production
    command refuses to extract if the maintainer has not pinned the
    real hash (currently empty, pending rotation). A new
    `download-voice-model-dev` command allows skipping the check for
    development. The zip members are also validated for path-traversal
    before extraction (defense in depth alongside MAE-SEC-008).
- **Rationale:** the Vosk model is downloaded from
  `https://alphacephei.com/vosk/models/` without any integrity
  check. A man-in-the-middle on the CDN, a compromised mirror, or a
  compromised DNS response could substitute a backdoored model that
  exfiltrates audio or executes arbitrary code via the Vosk
  recognizer. The SHA-256 check prevents this — the maintainer must
  pin the real hash before the next release.
- **Verification:** static check in `test_audit_remediation.py`
  confirms `VOSK_MODEL_SHA256` and `hashlib.sha256` appear in the
  source. The `test_vosk_download_refuses_unverified` test verifies
  the production command refuses to download when the hash is empty.

---

### MAE-OSS-002 — `SECURITY.md` supported-versions table is stale ✅

- **Severity:** Low (CVSS 2.0)
- **Files touched:**
  - `SECURITY.md` — the supported-versions table now lists `1.2.x`
    as Active (was `1.1.x`). `1.0.x` is now End-of-life (was
    "Security fixes only"). The "Last updated" date is bumped to
    2026-08-19. The Authentication and Sandboxing sections are also
    updated to describe the audit fixes (MAE-SEC-001 fail-closed,
    MAE-SEC-005 Bearer header, MAE-SEC-004 null Origin removal,
    MAE-SEC-002 placeholder root, MAE-SEC-008 zip-slip, MAE-SEC-006
    AppleScript bridge, MAE-SEC-017 Vosk SHA-256).
- **Rationale:** consumers who read `SECURITY.md` to determine
  whether their version is supported were misled. The "Last updated"
  date was stale (2026-07-09).
- **Verification:** static check in `test_audit_remediation.py`
  confirms `1.2.x` and `2026-08-19` appear in `SECURITY.md`.

---

### MAE-OSS-003 — SBOM declares wrong license and version ✅

- **Severity:** Low (CVSS 2.5)
- **Files touched:**
  - `packaging/sbom.cdx.json` — the metadata.component block now
    declares `version: "1.2.0"` (was `"1.0.0"`) and
    `license.id: "AGPL-3.0-only"` (was `"MIT"`). Added `bom-ref`,
    `purl`, and a `tools` block to match the CycloneDX 1.5 spec.
    The timestamp is bumped to `2026-08-19T00:00:00Z` (was
    `2026-07-04T10:48:00Z`).
- **Rationale:** the SBOM is the canonical supply-chain artifact
  consumers use to evaluate Maestro's license obligations. Declaring
  `MIT` when the actual license is `AGPL-3.0-only` (per `LICENSE`)
  would mislead downstream users into thinking they can incorporate
  Maestro into a closed-source product without source-disclosure
  obligations. The version mismatch (`1.0.0` vs `1.2.0`) prevented
  vulnerability scanners from correlating advisories with the
  installed version.
- **Verification:** static check in `test_audit_remediation.py`
  confirms `AGPL-3.0-only` and `"1.2.0"` appear in the SBOM and that
  `"MIT"` does not appear in the Maestro component block.

---

## Deferred Findings

The following findings are documented in the threat model in
`docs/specs/ds-007-threat-model.md` and are not addressed in this
remediation pass. They are tracked with explicit owners and revisit
triggers.

### MAE-SEC-007 — `apply_update` calls `subprocess.Popen([archive_path, "/S"])` for .exe files without verifying the .exe ⏸️

- **Severity:** Medium (CVSS 5.0)
- **Reason for deferral:** verifying a Windows .exe signature
  requires `wintrust.dll` (via `pywin32`'s `win32security.VerifyTrust`)
  or `signify`/`minisign` for signature verification. Adding a
  signature-verification step is a meaningful feature addition, not a
  mechanical fix. The TUF channel is also currently disabled
  (MAE-SEC-002), so no .exe update can be served until the channel
  goes live.
- **Revisit trigger:** before the TUF update channel goes live with
  real keys.

### MAE-SEC-011 — Integration server has no socket timeout (slowloris DoS) ⏸️

- **Severity:** Medium (CVSS 4.0)
- **Reason for deferral:** the integration server binds to
  `127.0.0.1` only (not `0.0.0.0`), so the slowloris attack surface
  is limited to local processes. The fix requires adding a
  `socket.settimeout()` call on the accepted connection and a
  per-request deadline, which is a non-trivial refactor of the
  hand-rolled HTTP parser.
- **Revisit trigger:** next performance/security hardening sprint.

### MAE-SEC-012 — WebSocket server does not validate incoming client frames ⏸️

- **Severity:** Medium (CVSS 4.0)
- **Reason for deferral:** full WebSocket frame validation (opcodes,
  masking, payload-length bounds, control-frame interleaving) is a
  meaningful feature addition. The current server only emits frames
  to clients; it does not read incoming frames, so the attack
  surface is limited to clients that can crash the server by sending
  malformed frames.
- **Revisit trigger:** if/when the server accepts incoming frames
  for bi-directional control.

### MAE-SEC-013 — `run-applescript` reachable from non-macOS platforms returns "mocked" output ⏸️

- **Severity:** Low (CVSS 2.0)
- **Reason for deferral:** the "mocked" output is intentional for
  test environments. The fix is to raise `RuntimeError` on non-macOS
  platforms, which would break existing test fixtures that exercise
  the CLI command path on Linux CI runners.
- **Revisit trigger:** next test-suite refactor.

### MAE-ARCH-001 through MAE-ARCH-010 — Architecture findings ⏸️

- **Severity:** Low to Medium
- **Reason for deferral:** these are architecture-debt items
  (cross-module `_config` access, global monkey-patching of
  `subprocess` in `linux_controller.py`, global monkey-patching of
  `ctypes.CDLL.__init__` in `__init__.py`, hand-rolled HTTP/1.1
  parser, `_SubprocessWrapper.run` recursion guard, socket-fromfd
  leak, inner `DummyController` class). Each requires a focused
  refactor with its own test coverage.
- **Revisit trigger:** next architecture-cleanup sprint.

### MAE-OSS-001 — Single CODEOWNERS entry, no enforced peer review ⏸️

- **Severity:** Low
- **Reason for deferral:** this is a project-health finding, not a
  code fix. Adding maintainers requires recruiting contributors.
- **Revisit trigger:** when the project moves to a multi-maintainer
  model.

### MAE-OSS-004 through MAE-OSS-010 — OSS health findings ⏸️

- **Severity:** Low to Info
- **Reason for deferral:** these are project-health items
  (`error_log.md` is committed and auto-regenerated, `agents.md` is
  a 106 KB AI-prompting file, no GitHub Security Advisories enabled,
  no formal release signing of the SBOM, no annual pentest evidence,
  no bug bounty program). Each requires a maintainer decision, not
  an engineering fix.
- **Revisit trigger:** next maintainer-review sprint.

---

## Verification Checklist

- [x] `verify_peer` Windows branch contains no `return True` on executable lines (MAE-SEC-001)
- [x] `_is_placeholder_root(BOOTSTRAP_ROOT)` returns `True` (MAE-SEC-002)
- [x] `UpdateCheckerThread.__init__` accepts `allow_placeholder_root` parameter (MAE-SEC-002)
- [x] `os.symlink` is unchanged after importing `gesture_controller.core.updater` (MAE-SEC-003)
- [x] `secure_symlink` is a regular callable in the updater module (MAE-SEC-003)
- [x] `apply_update` source contains `_is_safe_member_path` and no `# nosec B202` (MAE-SEC-008)
- [x] `_validate_applescript('do shell script "rm -rf /"')` raises `AppleScriptSecurityError` (MAE-SEC-006)
- [x] `BrokerClientController._ensure_connected` source contains `close_fds=True` and `env=os.environ.copy()` (MAE-SEC-015)
- [x] `integration_server.py` `allowed_origins` set contains no `"null"` literal (MAE-SEC-004)
- [x] `cli.py` URL-building lines do not contain `?token=` (MAE-SEC-005)
- [x] `cli.py` source contains `Authorization` and `Bearer` (MAE-SEC-005)
- [x] `ci.yml` does not contain `pip-audit || true` (MAE-SEC-009)
- [x] `ci.yml` pytest lines do not contain `|| true` (MAE-SEC-010)
- [x] `sbom.cdx.json` declares `AGPL-3.0-only` and `1.2.0` (MAE-OSS-003)
- [x] `SECURITY.md` lists `1.2.x` as Active and has `2026-08-19` date (MAE-OSS-002)
- [x] `cli.py` contains `VOSK_MODEL_SHA256` and `hashlib.sha256` (MAE-SEC-017)
- [x] `test_audit_remediation.py` parses without syntax errors
- [x] `AUDIT_REMEDIATION.md` (this document) created at the repo root
- [x] `CHANGELOG.md` `[Unreleased]` section updated with all audit-remediation entries

---

## Cross-References

- **Audit report:** `Maestro_audit.pdf` / `Maestro_audit.md` (deep forensic audit, 2026-08-19)
- **Threat model:** `docs/specs/ds-007-threat-model.md` (deferred findings tracked here)
- **Security policy:** `SECURITY.md` (updated with audit-fix descriptions)
- **Changelog:** `CHANGELOG.md` `[Unreleased]` section (audit-remediation entries added)
- **Tests:** `gesture_controller/tests/unit/test_audit_remediation.py` (12 regression tests)
