import socket
import threading
import json
import base64
import hashlib
import urllib.parse
import structlog
from typing import Any, List, Optional

from gesture_controller.core.event_bus import EventBus
from gesture_controller.models.data_types import GestureEvent

logger = structlog.get_logger(__name__)


def calculate_ws_accept(key: str) -> str:
    """Calculate the WebSocket accept key according to RFC 6455."""
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    accept_hash = hashlib.sha1((key.strip() + guid).encode("utf-8")).digest()  # nosec B324
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

            # Authenticate using constant-time comparison
            client_token = token_param or token_header
            if not client_token or not secrets.compare_digest(client_token, self.token):
                self._send_http_response(conn, 401, {"error": "Unauthorized"})
                conn.close()
                return

            # Check if this is a WebSocket upgrade request
            if headers.get("upgrade", "").lower() == "websocket" and "sec-websocket-key" in headers:
                origin = headers.get("origin", "")
                allowed_origins = {
                    "http://localhost:8765",
                    "http://127.0.0.1:8765",
                    "null",
                }
                if origin and origin not in allowed_origins:
                    logger.warning("WebSocket handshake rejected: bad Origin header", origin=origin)
                    self._send_http_response(conn, 403, {"error": "Forbidden - Origin not allowed"})
                    conn.close()
                    return

                self._handle_websocket_handshake(conn, headers["sec-websocket-key"])
                return

            # Read full POST body if needed
            body = ""
            if method == "POST":
                content_length = int(headers.get("content-length", 0))
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
                    safe = stage.replace(" ", "_").replace("-", "_")
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
