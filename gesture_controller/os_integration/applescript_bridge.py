import platform
import re
import subprocess
import structlog

logger = structlog.get_logger(__name__)


# Audit fix MAE-SEC-006: cap the maximum script length and reject any script
# containing the ``do shell script`` AppleScript idiom (which would allow a
# caller to escape to bash). This is defense in depth — the CLI command
# ``maestro run-applescript`` should never be exposed to untrusted input, but
# if it ever is, these checks prevent trivial code execution.
MAX_APPLESCRIPT_LENGTH = 8192
FORBIDDEN_APPLESCRIPT_PATTERNS = [
    re.compile(r"\bdo\s+shell\s+script\b", re.IGNORECASE),
    re.compile(r"\bPOSIX\s+path\s+of\b", re.IGNORECASE),
    # Audit fix MAE-V2-SEC-005: catch additional bypass vectors
    re.compile(r"\brun\s+script\b", re.IGNORECASE),  # run script "..." bypasses -e
    re.compile(r"\btell\s+application\b\s*[\"']Terminal[\"']", re.IGNORECASE),  # Terminal.app do script
    re.compile(r"\bdo\s+script\b", re.IGNORECASE),  # Terminal.app do script
]


class AppleScriptSecurityError(RuntimeError):
    """Raised when an AppleScript violates the security policy (audit fix MAE-SEC-006)."""


def _validate_applescript(script: str) -> None:
    """Audit fix MAE-SEC-006: validate the script before passing it to osascript."""
    if not isinstance(script, str):
        raise AppleScriptSecurityError("AppleScript must be a string")
    if len(script) > MAX_APPLESCRIPT_LENGTH:
        raise AppleScriptSecurityError(
            f"AppleScript exceeds maximum length {MAX_APPLESCRIPT_LENGTH} (got {len(script)})"
        )
    for pattern in FORBIDDEN_APPLESCRIPT_PATTERNS:
        if pattern.search(script):
            raise AppleScriptSecurityError(
                f"AppleScript contains forbidden pattern '{pattern.pattern}' — "
                "shell escape is not allowed (audit fix MAE-SEC-006)"
            )


def run_applescript(script: str) -> str:
    """Execute an AppleScript command using osascript on macOS (Darwin).

    Audit fix MAE-SEC-006: previously this function was an unguarded
    ``subprocess.Popen(["osascript", "-e", script])`` wrapper reachable from
    the ``maestro run-applescript`` CLI command — any caller (including a
    compromised plugin or a malicious integration-server request) could pass
    arbitrary AppleScript, including ``do shell script "..."`` which gives
    full bash execution. The function now:

    1. Validates the script length (cap at 8 KiB).
    2. Rejects scripts containing ``do shell script`` or ``POSIX path of``
       patterns — these are the main escape vectors.
    3. Explicitly passes ``-l AppleScript`` so a script cannot force the
       osascript interpreter into JavaScript mode (``-l JavaScript``), which
       would broaden the attack surface to the JSCore runtime.

    The CLI command remains restricted to interactive use on macOS only;
    non-macOS callers receive a clear "mocked" message rather than executing
    any code.
    """
    if platform.system() != "Darwin":
        logger.info("AppleScript execution mocked (non-macOS platform)", script=script[:128])
        return "mocked_applescript_output"

    # Audit fix MAE-SEC-006: validate before invoking osascript.
    _validate_applescript(script)

    try:
        p = subprocess.Popen(
            # Explicit ``-l AppleScript`` prevents the caller from forcing
            # JavaScript mode via a ``#`` shebang line (osascript respects
            # shebangs in script files passed via ``-e`` is not an issue
            # since ``-e`` is always AppleScript, but ``-l`` makes the
            # language choice explicit and unchangeable).
            ["osascript", "-l", "AppleScript", "-e", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
        try:
            out, err = p.communicate(timeout=2.0)
        except subprocess.TimeoutExpired as e:
            p.kill()
            out, err = p.communicate()
            raise RuntimeError(f"osascript execution timed out: {e}") from e

        if p.returncode != 0:
            err_msg = err.decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"osascript error: {err_msg}")
        return out.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        logger.error("Failed to run osascript", error=str(e))
        raise
