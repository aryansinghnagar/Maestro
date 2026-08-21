import os
import sys
import json
import time
import platform
import hashlib
import threading
import structlog
from pathlib import Path
from collections import deque
from typing import Any, Dict, List, Optional
from multiprocessing.connection import Listener, Client

from gesture_controller.os_integration.base_controller import BaseController

logger = structlog.get_logger(__name__)


def get_broker_address() -> str:
    if platform.system() == "Windows":
        return r"\\.\pipe\gesture_controller_broker"
    else:
        from gesture_controller.core.paths import broker_socket_path

        p = broker_socket_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)


def get_broker_family() -> str:
    return "AF_PIPE" if platform.system() == "Windows" else "AF_UNIX"


def verify_peer(conn: Any) -> bool:
    """Verify that the connecting peer process belongs to the same UID.

    Audit fix MAE-SEC-001: previously the Windows path returned ``True`` if any
    exception was raised during the SID lookup, which fail-open behavior meant
    any local Windows process could connect to the named pipe and inject
    arbitrary input. The function now fail-closes (returns ``False``) on any
    exception, logs at ERROR level, and writes an audit-log entry. The Linux
    and macOS paths already failed closed.
    """
    if platform.system() == "Windows":
        try:
            import win32security  # type: ignore[import-untyped]
            import win32api  # type: ignore[import-untyped]
            import ctypes

            token_handle = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
            )
            current_sid, _ = win32security.GetTokenInformation(
                token_handle, win32security.TokenUser
            )

            handle = conn.fileno()
            client_pid = ctypes.c_ulong()
            windll = getattr(ctypes, "windll", None)
            kernel32 = getattr(windll, "kernel32", None) if windll else None
            if kernel32 and hasattr(kernel32, "GetNamedPipeClientProcessId"):
                if kernel32.GetNamedPipeClientProcessId(handle, ctypes.byref(client_pid)):
                    client_proc = win32api.OpenProcess(0x0400, False, client_pid.value)
                    client_token = win32security.OpenProcessToken(
                        client_proc, win32security.TOKEN_QUERY
                    )
                    client_sid, _ = win32security.GetTokenInformation(
                        client_token, win32security.TokenUser
                    )
                    return bool(current_sid == client_sid)
            # Audit fix MAE-SEC-001: if we fell through without returning,
            # we failed to obtain or compare SIDs. Fail closed.
            logger.error(
                "Windows peer verification: unable to query peer SID; connection rejected",
                handle=handle,
            )
            return False
        except Exception as e:
            # Audit fix MAE-SEC-001: ALWAYS fail closed. Previously we
            # returned True when win32security/win32api were not importable
            # or any other exception was raised.
            logger.error(
                "Windows peer verification failed; connection rejected",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    import socket
    import struct

    # Audit fix MAE-ARCH-009: ``socket.fromfd`` *duplicates* the underlying
    # file descriptor — the original ``conn`` still holds its own reference,
    # so we must close the duplicate ``s`` once we're done inspecting peer
    # credentials. Previously the duplicate was leaked on every connection,
    # slowly exhausting the per-process file-descriptor table under high
    # gesture frequency (each broker client = one leaked fd).
    s: Optional[socket.socket] = None
    try:
        af_unix = getattr(socket, "AF_UNIX", 1)
        fd = conn.fileno()
        s = socket.fromfd(fd, af_unix, socket.SOCK_STREAM)
        getuid_fn = getattr(os, "getuid", lambda: -1)

        if platform.system() == "Linux":
            so_peercred = int(getattr(socket, "SO_PEERCRED", 17))
            cred = s.getsockopt(socket.SOL_SOCKET, so_peercred, struct.calcsize("3i"))
            _, uid, _ = struct.unpack("3i", cred)
            return bool(uid == getuid_fn())

        elif platform.system() == "Darwin":
            sol_local = int(getattr(socket, "SOL_LOCAL", 0))
            local_peercred = int(getattr(socket, "LOCAL_PEERCRED", 1))
            cred = s.getsockopt(sol_local, local_peercred, 128)
            # macOS struct xucred: cr_version (uint32), cr_uid (uid_t/uint32), cr_ngroups (short), ...
            _, uid = struct.unpack("=II", cred[:8])
            return bool(uid == getuid_fn())
    except Exception as e:
        logger.error("Peer verification failed", error=str(e))
        return False
    finally:
        # Audit fix MAE-ARCH-009: ALWAYS close the duplicate socket,
        # whether we returned True, returned False, or raised.
        if s is not None:
            try:
                s.close()
            except Exception:
                pass
    return False


class RateLimiter:
    """Token-bucket-ish rate limiter for broker input actions.

    Audit fix (perf P4): all deques now use ``maxlen`` so memory is bounded
    even if the manual ``popleft`` eviction were ever skipped (e.g., on
    exception). The ``maxlen`` values are sized to the *theoretical* maximum
    per-window count, so auto-eviction never fires under normal operation —
    the explicit ``if len() >= max_*`` checks still drive the verdict.
    The bound purely defends against unbounded growth if clock skew or a
    logic bug ever caused timestamps to be recorded without old ones being
    evicted.
    """

    # Per-window theoretical maxima (used as deque maxlen).
    _GLOBAL_MAXLEN = 128  # > max_global (120)
    _BURST_MAXLEN = 32  # > max_burst (30)
    _PER_GESTURE_MAXLEN = 8  # > 5/gesture/sec

    def __init__(self) -> None:
        self.global_history: deque[float] = deque(maxlen=self._GLOBAL_MAXLEN)
        self.gesture_history: dict[str, deque[float]] = {}
        self.burst_history: deque[float] = deque(maxlen=self._BURST_MAXLEN)

    def check_and_record(self, gesture_id: Optional[str]) -> bool:
        now = time.monotonic()

        max_global = 120 if gesture_id in ("mouse_move", "MouseScroll") else 30
        max_burst = 30 if gesture_id in ("mouse_move", "MouseScroll") else 10

        # 1. Global rate limit
        while self.global_history and now - self.global_history[0] > 1.0:
            self.global_history.popleft()
        if len(self.global_history) >= max_global:
            return False

        # 2. Burst limit
        while self.burst_history and now - self.burst_history[0] > 0.1:
            self.burst_history.popleft()
        if len(self.burst_history) >= max_burst:
            return False

        # 3. Per-gesture rate limit: 5 actions/sec
        if gesture_id:
            history = self.gesture_history.get(gesture_id)
            if history is None:
                history = deque(maxlen=self._PER_GESTURE_MAXLEN)
                self.gesture_history[gesture_id] = history
            while history and now - history[0] > 1.0:
                history.popleft()
            if len(history) >= 5:
                return False

        # Record action timestamp
        self.global_history.append(now)
        self.burst_history.append(now)
        if gesture_id:
            self.gesture_history[gesture_id].append(now)
        return True


class AuditLogger:
    """Append-only, hash-chained audit log with buffered writes.

    Audit fix (perf P5): previously every ``log()`` call opened the file,
    wrote one JSON line, and closed it (forcing an fsync on most filesystems).
    Under high-frequency gesture sequences (e.g., 60 fps mouse_move) this
    incurred ~1 ms of I/O per event — up to 60 ms/sec of fsync overhead.

    The new implementation buffers up to ``_FLUSH_BATCH`` entries or
    ``_FLUSH_INTERVAL_SECONDS`` elapsed time (whichever comes first) and
    flushes them in a single ``write()`` call. The hash chain remains
    sequential because all updates are made under ``self._lock``. A
    ``flush()`` is exposed for graceful shutdown.
    """

    _FLUSH_BATCH = 10
    _FLUSH_INTERVAL_SECONDS = 0.100

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.last_hash = "0" * 64
        self._lock = threading.Lock()
        self._buffer: list[str] = []
        self._last_flush = time.monotonic()
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last_line = json.loads(lines[-1])
                        self.last_hash = last_line.get("hash", "0" * 64)
            except Exception:
                pass

    def log(self, event_type: str, details: dict[str, Any]) -> None:
        with self._lock:
            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            entry = {
                "timestamp": now_str,
                "event": event_type,
                "details": details,
                "prev_hash": self.last_hash,
            }
            entry_json = json.dumps(entry, sort_keys=True)
            current_hash = hashlib.sha256(entry_json.encode("utf-8")).hexdigest()
            entry["hash"] = current_hash
            self.last_hash = current_hash

            self._buffer.append(json.dumps(entry))
            if (
                len(self._buffer) >= self._FLUSH_BATCH
                or (time.monotonic() - self._last_flush) >= self._FLUSH_INTERVAL_SECONDS
            ):
                self._flush_locked()

    def _flush_locked(self) -> None:
        """Write all buffered entries to disk. Caller must hold ``self._lock``."""
        if not self._buffer:
            return
        payload = "".join(line + "\n" for line in self._buffer)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    # fsync may fail on some filesystems (tmpfs, network FS);
                    # the flush() above is still a sufficient durability
                    # guarantee for the audit-log threat model.
                    pass
        except Exception as e:
            logger.error("Audit log write failed", error=str(e), dropped=len(self._buffer))
        finally:
            self._buffer.clear()
            self._last_flush = time.monotonic()

    def flush(self) -> None:
        """Force any buffered entries to disk. Idempotent."""
        with self._lock:
            self._flush_locked()


class InjectionBrokerServer:
    def __init__(self, address: Optional[str] = None) -> None:
        self.address = address or get_broker_address()
        self.family = get_broker_family()
        self.rate_limiter = RateLimiter()

        from gesture_controller.core.paths import user_config_dir

        log_dir = user_config_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        self.audit_logger = AuditLogger(log_dir / "audit.log")
        self.kill_switch_active = False
        self.esc_presses: List[float] = []

        # Instantiate actual OS controller (use_broker=False)
        from gesture_controller.os_integration import create_controller

        self.controller = create_controller(use_broker=False)
        self.running = False
        self._listener: Optional[Listener] = None

    def start(self) -> None:
        # Clean up existing Unix socket file if present
        if self.family == "AF_UNIX" and os.path.exists(self.address):
            try:
                os.remove(self.address)
            except Exception:
                pass

        logger.info("Starting input injection broker", address=self.address)
        self._listener = Listener(self.address, self.family)
        self.running = True
        self.audit_logger.log("broker_started", {"address": self.address})

        try:
            while self.running:
                try:
                    conn = self._listener.accept()
                    if not verify_peer(conn):
                        logger.warning("Rejected unauthorized broker connection attempt")
                        self.audit_logger.log("auth_rejected", {"reason": "unauthorized_uid"})
                        conn.close()
                        continue
                    threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
                except Exception as e:
                    if self.running:
                        logger.error("Error accepting connection", error=str(e))
        finally:
            self._listener.close()

    def stop(self) -> None:
        self.running = False
        if self._listener:
            try:
                self._listener.close()
            except Exception:
                pass
        if self.family == "AF_UNIX" and os.path.exists(self.address):
            try:
                os.remove(self.address)
            except Exception:
                pass
        self.audit_logger.log("broker_stopped", {})
        # Audit fix (perf P5): drain any buffered entries to disk so the
        # final "broker_stopped" record and any pending high-frequency
        # events are not lost on shutdown.
        self.audit_logger.flush()

    def _handle_client(self, conn: Any) -> None:
        try:
            while self.running:
                try:
                    msg_bytes = conn.recv_bytes()
                    if not msg_bytes:
                        break
                    req = json.loads(msg_bytes.decode("utf-8"))
                    res = self.handle_request(req)
                    conn.send_bytes(json.dumps(res).encode("utf-8"))
                except (EOFError, ConnectionResetError):
                    break
                except Exception as e:
                    logger.error("Error handling client request", error=str(e))
                    break
        finally:
            conn.close()

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any]:
        action = req.get("action")
        gesture_id = req.get("gesture_id")
        if isinstance(gesture_id, str):
            gesture_str: Optional[str] = gesture_id
        else:
            gesture_str = None

        if action == "set_kill_switch":
            active = bool(req.get("active", False))
            self.kill_switch_active = active
            self.audit_logger.log("kill_switch_changed", {"active": active})
            return {"status": "ok"}

        if action == "get_kill_switch_state":
            return {"status": "ok", "active": self.kill_switch_active}

        if self.kill_switch_active:
            self.audit_logger.log("blocked_by_kill_switch", {"method": str(action)})
            return {"status": "kill_switch_active"}

        method_name = req.get("method")
        args = req.get("args", {})

        if not isinstance(method_name, str):
            return {"status": "error", "message": "Method name must be a string"}

        if not hasattr(self.controller, method_name):
            return {"status": "error", "message": f"Method {method_name} not supported"}

        if not self.rate_limiter.check_and_record(gesture_str):
            self.audit_logger.log(
                "rate_limited", {"method": method_name, "gesture_id": gesture_str}
            )
            return {"status": "rate_limited"}

        # Esc x 3 detection
        if method_name == "key_combo" and args.get("keys") == ["escape"]:
            self._handle_esc_press()
        elif method_name == "key_press" and args.get("key") == "escape":
            self._handle_esc_press()

        self.audit_logger.log(
            "action_executed", {"method": method_name, "args": args, "gesture_id": gesture_str}
        )

        try:
            method = getattr(self.controller, method_name)

            # Call controller method dynamically
            if method_name in ("key_press", "key_release"):
                method(args.get("key"), **{k: v for k, v in args.items() if k != "key"})
            elif method_name == "key_combo":
                method(args.get("keys"))
            elif method_name in ("mouse_click", "mouse_double_click"):
                method(**args)
            elif method_name == "mouse_move":
                method(args.get("x"), args.get("y"), args.get("absolute", True))
            elif method_name == "mouse_scroll":
                method(args.get("delta_x", 0), args.get("delta_y", 0))
            elif method_name in (
                "get_foreground_app",
                "minimize_active_window",
                "switch_window",
                "show_desktop",
                "media_play_pause",
                "media_next",
                "media_previous",
                "media_volume_up",
                "media_volume_down",
            ):
                res = method()
                if method_name == "get_foreground_app":
                    return {"status": "ok", "result": res}
            else:
                method(**args)

            return {"status": "ok"}
        except Exception as e:
            logger.error("Broker failed to execute action", method=method_name, error=str(e))
            return {"status": "error", "message": str(e)}

    def _handle_esc_press(self) -> None:
        now = time.monotonic()
        self.esc_presses = [t for t in self.esc_presses if now - t <= 1.0]
        self.esc_presses.append(now)
        if len(self.esc_presses) >= 3:
            self.kill_switch_active = True
            self.esc_presses.clear()
            self.audit_logger.log("kill_switch_triggered_by_hotkey", {})
            logger.warn("Broker kill switch activated by ESC x 3 keypresses")


class BrokerClientController(BaseController):
    """Client controller proxying input injection commands to InjectionBrokerServer (S3-12)."""

    _local_context = threading.local()

    def __init__(self) -> None:
        self.address = get_broker_address()
        self.family = get_broker_family()
        self._conn: Any = None
        self._lock = threading.Lock()
        self._ensure_connected()

    @classmethod
    def set_active_gesture(cls, gesture_name: Optional[str]) -> None:
        cls._local_context.active_gesture = gesture_name

    @classmethod
    def get_active_gesture(cls) -> Optional[str]:
        return getattr(cls._local_context, "active_gesture", None)

    def _ensure_connected(self) -> bool:
        if self._conn:
            return True

        with self._lock:
            # Try connecting to existing broker
            try:
                self._conn = Client(self.address, self.family)
                return True
            except Exception:
                pass

            # If not running, spawn server process in background
            try:
                import subprocess

                # Audit fix MAE-SEC-015: explicitly pass ``close_fds=True``
                # so the broker subprocess does not inherit unrelated file
                # descriptors (camera SHM, integration server sockets,
                # opened log files, etc.). Also pass ``env=os.environ.copy()``
                # so the broker inherits a deterministic environment rather
                # than the (potentially mutated) live environment.
                subprocess.Popen(
                    [sys.executable, "-m", "gesture_controller.os_integration.broker"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    env=os.environ.copy(),
                    creationflags=(
                        getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                        if platform.system() == "Windows"
                        else 0
                    ),
                )

                # Retry connection loop (up to 3 seconds)
                for _ in range(30):
                    time.sleep(0.1)
                    try:
                        self._conn = Client(self.address, self.family)
                        return True
                    except Exception:
                        pass
            except Exception as e:
                logger.error("Failed to spawn background broker", error=str(e))

        return False

    def _send_request(self, method_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if not self._ensure_connected():
            return {"status": "error", "message": "Failed to connect to broker"}

        req = {
            "action": "input_action",
            "method": method_name,
            "args": args,
            "gesture_id": self.get_active_gesture(),
        }

        with self._lock:
            try:
                self._conn.send_bytes(json.dumps(req).encode("utf-8"))
                res_bytes = self._conn.recv_bytes()
                res = json.loads(res_bytes.decode("utf-8"))
                if isinstance(res, dict):
                    return res
            except Exception as e:
                logger.error("Broker connection error, retrying...", error=str(e))
                self._conn = None

        # Retry once
        if self._ensure_connected():
            with self._lock:
                try:
                    self._conn.send_bytes(json.dumps(req).encode("utf-8"))
                    res_bytes = self._conn.recv_bytes()
                    res = json.loads(res_bytes.decode("utf-8"))
                    if isinstance(res, dict):
                        return res
                except Exception:
                    self._conn = None

        return {"status": "error", "message": "Broker connection lost"}

    def is_supported(self) -> bool:
        return True

    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        self._send_request("key_press", {"key": key, "modifiers": modifiers or []})

    def key_release(self, key: str) -> None:
        self._send_request("key_release", {"key": key})

    def key_combo(self, keys: list[str]) -> None:
        self._send_request("key_combo", {"keys": keys})

    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        self._send_request("mouse_click", {"button": button, "x": x, "y": y})

    def mouse_double_click(
        self, button: str = "left", x: int | None = None, y: int | None = None
    ) -> None:
        self._send_request("mouse_double_click", {"button": button, "x": x, "y": y})

    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
        self._send_request("mouse_move", {"x": x, "y": y, "absolute": absolute})

    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
        self._send_request("mouse_scroll", {"delta_x": delta_x, "delta_y": delta_y})

    def get_foreground_app(self) -> str:
        res = self._send_request("get_foreground_app", {})
        result = res.get("result", "unknown")
        return str(result)

    def minimize_active_window(self) -> None:
        self._send_request("minimize_active_window", {})

    def switch_window(self) -> None:
        self._send_request("switch_window", {})

    def show_desktop(self) -> None:
        self._send_request("show_desktop", {})

    def media_play_pause(self) -> None:
        self._send_request("media_play_pause", {})

    def media_next(self) -> None:
        self._send_request("media_next", {})

    def media_previous(self) -> None:
        self._send_request("media_previous", {})

    def media_volume_up(self) -> None:
        self._send_request("media_volume_up", {})

    def media_volume_down(self) -> None:
        self._send_request("media_volume_down", {})


if __name__ == "__main__":
    # If run directly, act as the broker server process
    try:
        server = InjectionBrokerServer()
        server.start()
    except KeyboardInterrupt:
        pass
