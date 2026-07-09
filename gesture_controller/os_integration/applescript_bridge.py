import platform
import subprocess
import structlog

logger = structlog.get_logger(__name__)


def run_applescript(script: str) -> str:
    """Execute an AppleScript command using osascript on macOS (Darwin)."""
    if platform.system() != "Darwin":
        logger.info("AppleScript execution mocked (non-macOS platform)", script=script)
        return "mocked_applescript_output"

    try:
        p = subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, err = p.communicate()
        if p.returncode != 0:
            err_msg = err.decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"osascript error: {err_msg}")
        return out.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        logger.error("Failed to run osascript", error=str(e))
        raise
