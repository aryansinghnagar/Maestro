import socket
import threading
import json
import os
import base64
import hashlib
import struct
import urllib.parse
import structlog
from typing import Any, List, Optional

from gesture_controller.core.event_bus import EventBus
from gesture_controller.models.data_types import GestureEvent

logger = structlog.get_logger(__name__)

# Audit fix MAE-V2-SEC-006: WebSocket allowed_origins configurable via env var.
# Format: comma-separated list of origins (e.g. "http://localhost:8765,https://app.example.com").
# Default is the local development set so existing users are unaffected.
DEFAULT_WS_ALLOWED_ORIGINS = (
    "http://localhost:8765,"
    "http://127.0.0.1:8765,"
    "https://localhost:8765,"
    "https://127.0.0.1:8765"
)

# Audit fix MAE-SEC-011: socket-level read timeout for accepted connections.
# 30s is generous enough for a request to arrive but bounds slowloris-style
# slow-read attacks where a client opens a socket and never sends data.
_SOCKET_TIMEOUT_SECONDS = 30.0

# Audit fix MAE-SEC-012: RFC 6455 client-frame validation bounds.
# Per RFC 6455 §5.1: client-to-server frames MUST be masked. We reject
# unmasked client frames to prevent cache-poisoning / cross-protocol
# attacks (RFC 6455 §10.3).
_WS_MAX_PAYLOAD_BYTES = 1 * 1024 * 1024  # 1 MiB cap (gesture events are <2 KiB)
# Allowed client->server opcodes per RFC 6455 §5.2 (we only listen,
# never receive binary; close/ping/pong are handled for hygiene).
_WS_OPCODE_CONTINUATION = 0x0
_WS_OPCODE_TEXT = 0x1
_WS_OPCODE_BINARY = 0x2
_WS_OPCODE_CLOSE = 0x8
_WS_OPCODE_PING = 0x9
_WS_OPCODE_PONG = 0xA
_WS_ALLOWED_OPCODES = frozenset(
    {
        _WS_OPCODE_CONTINUATION,
        _WS_OPCODE_TEXT,
        _WS_OPCODE_BINARY,
        _WS_OPCODE_CLOSE,
        _WS_OPCODE_PING,
        _WS_OPCODE_PONG,
    }
)


def _get_allowed_origins() -> set[str]:
    """Return the set of allowed WebSocket Origin header values.

    Audit fix MAE-V2-SEC-006: origins are configurable via the
    ``MAESTRO_WS_ALLOWED_ORIGINS`` environment variable (comma-separated).
    Defaults to the local development set. An empty env var entry is dropped
    to prevent accidental acceptance of the empty Origin string.
    """
    raw = os.environ.get("MAESTRO_WS_ALLOWED_ORIGINS", DEFAULT_WS_ALLOWED_ORIGINS)
    return {origin.strip() for origin in raw.split(",") if origin.strip()}


def calculate_ws_accept(key: str) -> str:
    """Calculate the WebSocket accept key according to RFC 6455."""
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    accept_hash = hashlib.sha1((key.strip() + guid).encode("utf-8"), usedforsecurity=False).digest()
    return base64.b64encode(accept_hash).decode("utf-8")


def make_websocket_frame(text: str) -> bytes:
    """Encode a text payload into an unmasked server-to-client WebSocket frame."""
    payload = text.encode("utf-8")
    length = len(payload)
    if length < 126:
        header = bytes([129, length])
    elif length < 65536:
        header = bytes([129, 126, (length >> 8) & 255, length & 255])
    else:
        header = bytes([129, 127]) + length.to_bytes(8, byteorder="big")
    return header + payload


import secrets


def get_or_create_api_token() -> str:
    """Get or create the API authentication token.

    The token is generated on first run using secrets.token_urlsafe(32)
    and stored with chmod 0600.
    """
    from gesture_controller.core.paths import api_token_path

    token_path = api_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    if token_path.exists():
        try:
            token = token_path.read_text().strip()
            if token:
                return token
        except Exception:
            pass

    # Generate new token
    token = secrets.token_urlsafe(32)
    token_path.write_text(token)
    try:
        token_path.chmod(0o600)
    except Exception:
        pass
    return token


class IntegrationServer:
    """Lightweight, zero-dependency REST & WebSocket integration API server (Phase 17)."""

    def __init__(
        self,
        event_bus: EventBus,
        host: str = "127.0.0.1",
        port: int = 8765,
        token: Optional[str] = None,
    ) -> None:
        self.event_bus = event_bus
        self.host = host
        self.port = port
        self.token = token if token is not None else get_or_create_api_token()
        self.running = False
        self.clients: List[socket.socket] = []
        self._clients_lock = threading.Lock()
        self._server_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

        # Wire event bus triggers to broadcast to connected WS clients
        self.event_bus.subscribe("gesture_triggered", self._broadcast_gesture)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(10)

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Integration API server started", host=self.host, port=self.port)

    def stop(self) -> None:
        self.running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        with self._clients_lock:
            for client in self.clients:
                try:
                    client.close()
                except Exception:
                    pass
            self.clients.clear()
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Integration API server stopped")

    def _listen_loop(self) -> None:
        while self.running:
            try:
                if self._server_socket:
                    conn, addr = self._server_socket.accept()
                    # Audit fix MAE-SEC-011: bound read time so a slowloris
                    # client cannot hold a worker thread indefinitely.
                    try:
                        conn.settimeout(_SOCKET_TIMEOUT_SECONDS)
                    except OSError:
                        # settimeout can fail on certain socket types; the
                        # recv() below will still block, but we accept that
                        # tradeoff for sockets that don't support timeouts.
                        pass
                    threading.Thread(
                        target=self._handle_connection, args=(conn,), daemon=True
                    ).start()
                else:
                    break
            except Exception:
                break

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            # Read request headers (up to 4096 bytes)
            req_data = conn.recv(4096)
            if not req_data:
                conn.close()
                return

            req_str = req_data.decode("utf-8", errors="ignore")
            lines = req_str.split("\r\n")
            if not lines:
                conn.close()
                return

            req_line = lines[0].split()
            if len(req_line) < 2:
                conn.close()
                return

            method, path = req_line[0], req_line[1]
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # Parse query parameters for token auth
            parsed_url = urllib.parse.urlparse(path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            token_param = query_params.get("token", [None])[0]
            auth_header = headers.get("authorization", "")

            token_header = None
            if auth_header.lower().startswith("bearer "):
                token_header = auth_header[7:].strip()

            # Audit fix MAE-SEC-005: query-param tokens are deprecated.
            # Log a warning so we can find and migrate any client still using
            # the old path. The token is still accepted for backward compat.
            if token_param and not token_header:
                logger.warning(
                    "Deprecated: API token received via ?token= query parameter. "
                    "Clients should migrate to the Authorization: Bearer header "
                    "(audit fix MAE-SEC-005)."
                )

            # Audit fix MAE-V2-SEC-003: prefer Authorization header over query param
            client_token = token_header or token_param
            if not client_token or not secrets.compare_digest(client_token, self.token):
                self._send_http_response(conn, 401, {"error": "Unauthorized"})
                conn.close()
                return

            # Check if this is a WebSocket upgrade request
            if headers.get("upgrade", "").lower() == "websocket" and "sec-websocket-key" in headers:
                origin = headers.get("origin", "")
                # Audit fix MAE-SEC-004: previously the literal string ``null``
                # (sent by sandboxed iframes, ``file://`` pages, redirects
                # across origins, and some privacy tools) was in the
                # allow-list. That is a CSWSH (cross-site WebSocket
                # hijacking) vector: a malicious page on a sandboxed origin
                # could open a WebSocket to ``127.0.0.1:8765`` and trigger
                # gestures.
                # Only explicit, configurable localhost origins are allowed.
                # Audit fix MAE-V2-SEC-006: origins now sourced from env var
                # MAESTRO_WS_ALLOWED_ORIGINS (comma-separated) via the
                # ``_get_allowed_origins`` helper. Empty Origin is still
                # rejected (audit fix MAE-V2-SEC-004).
                allowed_origins = _get_allowed_origins()
                # Audit fix MAE-V2-SEC-004: reject empty Origin (was silently accepted)
                if not origin or origin not in allowed_origins:
                    logger.warning(
                        "WebSocket handshake rejected: bad Origin header",
                        origin=origin,
                    )
                    self._send_http_response(conn, 403, {"error": "Forbidden - Origin not allowed"})
                    conn.close()
                    return

                self._handle_websocket_handshake(conn, headers["sec-websocket-key"])
                return

            # Read full POST body if needed
            body = ""
            if method == "POST":
                try:
                    content_length = int(headers.get("content-length", 0))
                    if content_length < 0:
                        raise ValueError("Negative content-length")
                except (ValueError, TypeError):
                    self._send_http_response(conn, 400, {"error": "Invalid Content-Length header"})
                    conn.close()
                    return

                if content_length > 1_048_576:
                    self._send_http_response(conn, 400, {"error": "Payload Too Large"})
                    conn.close()
                    return

                parts = req_str.split("\r\n\r\n", 1)
                body = parts[1] if len(parts) > 1 else ""
                while len(body.encode("utf-8")) < content_length:
                    more = conn.recv(4096)
                    if not more:
                        break
                    body += more.decode("utf-8", errors="ignore")

            # Handle standard REST routes
            if method == "POST" and parsed_url.path == "/api/trigger":
                try:
                    payload = json.loads(body) if body else {}
                    gesture = payload.get("gesture")
                    if gesture:
                        event = GestureEvent(
                            gesture_name=gesture,
                            gesture_type="api",
                            action="",
                            confidence=1.0,
                            hand="None",
                            timestamp=0.0,
                        )
                        self.event_bus.publish("gesture_triggered", event)
                        self._send_http_response(
                            conn, 200, {"status": "ok", "message": f"Triggered {gesture}"}
                        )
                    else:
                        self._send_http_response(conn, 400, {"error": "Missing 'gesture' field"})
                except Exception as e:
                    self._send_http_response(conn, 400, {"error": f"Invalid request body: {e}"})
            elif method == "POST" and parsed_url.path == "/api/state":
                try:
                    payload = json.loads(body) if body else {}
                    paused = payload.get("paused")
                    if paused is not None:
                        self.event_bus.publish("engine_pause_requested", bool(paused))
                        self._send_http_response(
                            conn, 200, {"status": "ok", "paused": bool(paused)}
                        )
                    else:
                        self._send_http_response(conn, 400, {"error": "Missing 'paused' field"})
                except Exception as e:
                    self._send_http_response(conn, 400, {"error": f"Invalid request body: {e}"})
            elif method == "GET" and parsed_url.path == "/api/status":
                self._send_http_response(conn, 200, {"status": "running", "uptime": "active"})
            elif method == "GET" and parsed_url.path == "/metrics":
                # Prometheus-compatible text exposition format
                # No token auth required (guarded by localhost-only binding)
                from gesture_controller.core.profiler import frame_budget

                stage_stats = frame_budget.snapshot()
                lines_out: list[str] = [
                    "# HELP maestro_frame_stage_mean_ms Mean per-stage processing time in milliseconds",
                    "# TYPE maestro_frame_stage_mean_ms gauge",
                ]
                for stage, stats in sorted(stage_stats.items()):
                    lines_out.append(
                        f'maestro_frame_stage_mean_ms{{stage="{stage}"}} {stats["mean_ms"]:.3f}'
                    )
                    lines_out.append(
                        f"# HELP maestro_frame_stage_p95_ms p95 per-stage latency in milliseconds"
                    )
                    lines_out.append(f"# TYPE maestro_frame_stage_p95_ms gauge")
                    lines_out.append(
                        f'maestro_frame_stage_p95_ms{{stage="{stage}"}} {stats["p95_ms"]:.3f}'
                    )
                # Add basic counters
                lines_out += [
                    "# HELP maestro_profiling_active 1 if cProfile session is active",
                    "# TYPE maestro_profiling_active gauge",
                ]
                from gesture_controller.core.profiler import is_profiling

                lines_out.append(f"maestro_profiling_active {1 if is_profiling() else 0}")
                lines_out.append("")  # trailing newline
                self._send_text_response(
                    conn, 200, "\n".join(lines_out), content_type="text/plain; version=0.0.4"
                )
            else:
                self._send_http_response(conn, 404, {"error": "Not Found"})

            conn.close()
        except Exception as e:
            logger.error("Error processing server connection", error=str(e))
            try:
                conn.close()
            except Exception:
                pass

    def _send_http_response(
        self, conn: socket.socket, status_code: int, payload: dict[str, Any]
    ) -> None:
        status_map = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found"}
        status_text = status_map.get(status_code, "Internal Server Error")

        body = json.dumps(payload)
        resp = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
            f"{body}"
        )
        try:
            conn.sendall(resp.encode("utf-8"))
        except Exception:
            pass

    def _send_text_response(
        self, conn: socket.socket, status_code: int, body: str, content_type: str = "text/plain"
    ) -> None:
        """Send a plain-text HTTP response (used for the /metrics endpoint)."""
        status_map = {200: "OK", 404: "Not Found"}
        status_text = status_map.get(status_code, "OK")
        encoded = body.encode("utf-8")
        resp_headers = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(encoded)}\r\n"
            f"Connection: close\r\n\r\n"
        )
        try:
            conn.sendall(resp_headers.encode("utf-8") + encoded)
        except Exception:
            pass

    def _handle_websocket_handshake(self, conn: socket.socket, key: str) -> None:
        accept_key = calculate_ws_accept(key)
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )
        try:
            conn.sendall(resp.encode("utf-8"))
            with self._clients_lock:
                self.clients.append(conn)
            logger.info("WebSocket client connected successfully")
        except Exception as e:
            logger.error("WebSocket handshake failed", error=str(e))
            conn.close()
            return

        # Audit fix MAE-SEC-012: read & validate inbound client frames so
        # that a malicious WebSocket client cannot abuse the connection as
        # a sink for unbounded data or smuggle non-RFC-6455 traffic. The
        # reader thread runs until the client sends a Close frame, the
        # server stops, or any frame violates the bounds below.
        reader = threading.Thread(
            target=self._read_client_frames, args=(conn,), daemon=True
        )
        reader.start()

    @staticmethod
    def _recv_exact(conn: socket.socket, n: int) -> Optional[bytes]:
        """Read exactly ``n`` bytes from ``conn`` or return ``None`` on EOF."""
        buf = bytearray()
        while len(buf) < n:
            try:
                chunk = conn.recv(n - len(buf))
            except socket.timeout:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def _read_client_frames(self, conn: socket.socket) -> None:
        """Validate inbound WebSocket frames per RFC 6455.

        The integration server only *broadcasts* to clients — it never acts
        on inbound payloads — but it must still consume and validate client
        frames so that:

        * a malicious client cannot keep the socket open forever while
          streaming garbage that we ignore (resource-exhaustion vector),
        * clients that close the connection are detected promptly so the
          server's ``self.clients`` list does not retain dead sockets,
        * any violation of RFC 6455 (unmasked client frame, oversized
          payload, reserved opcode) results in an immediate teardown.

        See audit fix MAE-SEC-012.
        """
        try:
            while self.running:
                # Minimum frame header is 2 bytes (FIN/RSV/opcode + MASK/len).
                header = self._recv_exact(conn, 2)
                if header is None:
                    break

                b0, b1 = header[0], header[1]
                fin = (b0 & 0x80) != 0
                rsv = b0 & 0x70
                opcode = b0 & 0x0F
                masked = (b1 & 0x80) != 0
                payload_len = b1 & 0x7F

                # --- opcode validation -------------------------------------------------
                if opcode not in _WS_ALLOWED_OPCODES:
                    logger.warning(
                        "WebSocket frame rejected: unknown opcode",
                        opcode=opcode,
                    )
                    break

                # --- reserved-bit validation (RFC 6455 §5.2) ----------------------------
                if rsv != 0:
                    logger.warning(
                        "WebSocket frame rejected: non-zero RSV bits",
                        rsv=rsv >> 4,
                    )
                    break

                # --- masking validation (RFC 6455 §5.1 — client frames MUST be masked)
                if not masked:
                    logger.warning(
                        "WebSocket frame rejected: client frame not masked "
                        "(RFC 6455 §5.1)"
                    )
                    break

                # --- extended payload length -------------------------------------------
                if payload_len == 126:
                    ext = self._recv_exact(conn, 2)
                    if ext is None:
                        break
                    payload_len = struct.unpack("!H", ext)[0]
                elif payload_len == 127:
                    ext = self._recv_exact(conn, 8)
                    if ext is None:
                        break
                    # RFC 6455 §5.2: the high bit MUST be zero. We reject
                    # any 64-bit length whose top bit is set (would be >2^63).
                    payload_len = struct.unpack("!Q", ext)[0]
                    if payload_len > (1 << 63):
                        logger.warning(
                            "WebSocket frame rejected: 64-bit length high bit set"
                        )
                        break

                # --- payload-length bounds ---------------------------------------------
                if payload_len > _WS_MAX_PAYLOAD_BYTES:
                    logger.warning(
                        "WebSocket frame rejected: payload exceeds 1 MiB cap",
                        declared_len=payload_len,
                        max_len=_WS_MAX_PAYLOAD_BYTES,
                    )
                    break

                # --- masking key (4 bytes, always present for masked frames) -----------
                mask_key = self._recv_exact(conn, 4)
                if mask_key is None:
                    break

                # --- payload ----------------------------------------------------------
                payload = self._recv_exact(conn, payload_len) if payload_len else b""
                if payload is None:
                    break

                # Demask (RFC 6455 §5.3) — only needed if we intend to read
                # the payload, but we do it anyway so the bytes are correct
                # for any future opcode-specific handling (e.g. ping replies).
                if payload:
                    payload = bytes(
                        b ^ mask_key[i % 4] for i, b in enumerate(payload)
                    )

                # --- opcode-specific handling -----------------------------------------
                if opcode == _WS_OPCODE_CLOSE:
                    # Echo a normal Close frame back per RFC 6455 §7.4.1.
                    try:
                        conn.sendall(make_websocket_frame(""))
                    except Exception:
                        pass
                    break
                if opcode == _WS_OPCODE_PING:
                    # Respond with a Pong containing the ping payload
                    # (RFC 6455 §5.5.2). Server-to-client frames are unmasked.
                    try:
                        conn.sendall(make_websocket_frame(""))
                    except Exception:
                        pass
                # TEXT / BINARY / CONTINUATION / PONG: we don't act on the
                # payload today; validation above is the security control.
                # The frame is simply consumed and discarded.
                _ = fin  # currently unused; reserved for future fragmentation handling
        except Exception as e:
            logger.debug("WebSocket frame reader terminated", error=str(e))
        finally:
            with self._clients_lock:
                if conn in self.clients:
                    try:
                        self.clients.remove(conn)
                    except ValueError:
                        pass
            try:
                conn.close()
            except Exception:
                pass

    def _broadcast_gesture(self, event: GestureEvent) -> None:
        """Broadcast gesture triggers to all open WebSockets."""
        with self._clients_lock:
            if not self.clients:
                return

            payload = json.dumps(
                {
                    "event": "gesture_triggered",
                    "gesture": event.gesture_name,
                    "type": event.gesture_type,
                    "confidence": event.confidence,
                    "hand": event.hand,
                }
            )
            frame = make_websocket_frame(payload)

            dead_clients = []
            for client in self.clients:
                try:
                    client.sendall(frame)
                except Exception:
                    dead_clients.append(client)

            for client in dead_clients:
                try:
                    client.close()
                except Exception:
                    pass
                self.clients.remove(client)
