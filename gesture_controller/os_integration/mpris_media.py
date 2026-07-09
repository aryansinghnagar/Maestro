import subprocess
import structlog
from typing import Any

logger = structlog.get_logger(__name__)


def _send_mpris_cmd(member: str) -> None:
    """Send MPRIS member command via D-Bus session bus."""
    # Method 1: Try importing dbus-next or dbus
    try:
        import dbus  # type: ignore[import-not-found]
        bus = dbus.SessionBus()
        # Find player service
        for service in bus.list_names():
            if service.startswith("org.mpris.MediaPlayer2."):
                player = bus.get_object(service, "/org/mpris/MediaPlayer2")
                if member == "PlayPause":
                    player.PlayPause(dbus_interface="org.mpris.MediaPlayer2.Player")
                elif member == "Next":
                    player.Next(dbus_interface="org.mpris.MediaPlayer2.Player")
                elif member == "Previous":
                    player.Previous(dbus_interface="org.mpris.MediaPlayer2.Player")
        return
    except Exception:
        pass

    # Method 2: Fallback to dbus-send utility (installed by default on Linux)
    try:
        # We query player names or broadcast to all active mpris players
        # The easiest is org.mpris.MediaPlayer2.Player method calls
        # We can find players via dbus-send or playerctl, or send to * standard destination.
        # But wait, dbus-send requires a specific destination.
        # So we can list mpris players or run dbus-send to all matches.
        # Let's run a quick find or broadcast.
        # We can list session bus services matching org.mpris.MediaPlayer2.
        p = subprocess.Popen(
            ["dbus-send", "--session", "--dest=org.freedesktop.DBus", "--type=method_call",
             "--print-reply", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        out, _ = p.communicate()
        if out:
            services = [
                s.strip().strip('"') for s in out.decode("utf-8", errors="ignore").split()
                if "org.mpris.MediaPlayer2" in s
            ]
            for service in services:
                # Clean name (remove string array markup)
                service_clean = service.replace("string", "").strip().strip('"')
                if service_clean.startswith("org.mpris.MediaPlayer2."):
                    subprocess.run([
                        "dbus-send", "--session", f"--dest={service_clean}",
                        "/org/mpris/MediaPlayer2", f"org.mpris.MediaPlayer2.Player.{member}"
                    ], capture_output=True)
            return
    except Exception as e:
        logger.warning("MPRIS dbus-send execution failed", error=str(e))

    # Method 3: Final fallback to playerctl
    try:
        cmd = "play-pause" if member == "PlayPause" else member.lower()
        subprocess.run(["playerctl", cmd], capture_output=True)
    except Exception:
        pass


def mpris_play_pause() -> None:
    _send_mpris_cmd("PlayPause")


def mpris_next() -> None:
    _send_mpris_cmd("Next")


def mpris_previous() -> None:
    _send_mpris_cmd("Previous")
