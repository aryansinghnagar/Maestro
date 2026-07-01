import cv2
import numpy as np
import multiprocessing as mp
from multiprocessing import shared_memory
import structlog
import time
from typing import Any

logger = structlog.get_logger(__name__)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_CHANNELS = 3
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * FRAME_CHANNELS

class CameraStream:
    """Process A: Captures frames from webcam and writes to SharedMemory."""

    def __init__(self, config: dict[str, Any], shm_name: str) -> None:
        self.config = config
        self.shm_name = shm_name
        self._running = False
        self._cap: cv2.VideoCapture | None = None
        self._backoff_idx = 0
        self._backoff_times = config.get("camera", {}).get(
            "reconnect_backoff_ms", [100, 200, 400, 800, 1600]
        )

    def run(self) -> None:
        """Main loop for the camera capture process."""
        self._running = True
        logger.info("Camera stream process started")
        while self._running:
            try:
                self._connect_camera()
                self._capture_loop()
            except Exception as e:
                if self._running:
                    logger.error("Camera error, attempting reconnect", error=str(e))
                    self._disconnect()
                    self._backoff_reconnect()
            time.sleep(0.01)
        logger.info("Camera stream process stopped")

    def _connect_camera(self) -> None:
        device_id = self.config.get("camera", {}).get("device_id", 0)
        backends = self.config.get("camera", {}).get("backend_preference", ["ANY"])

        self._cap = None
        # Add fallback to CAP_ANY if list is empty
        if not backends:
            backends = ["ANY"]

        for backend in backends:
            try:
                backend_val = getattr(cv2, f"CAP_{backend}", cv2.CAP_ANY)
                logger.info("Trying to open camera", device_id=device_id, backend=backend)
                cap = cv2.VideoCapture(device_id, backend_val)
                if cap.isOpened():
                    self._cap = cap
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, self.config.get("camera", {}).get("fps_target", 30))
                    logger.info("Camera connected successfully", backend=backend, device=device_id)
                    self._backoff_idx = 0
                    return
            except Exception as e:
                logger.debug("Failed opening camera with backend", backend=backend, error=str(e))
                continue

        # If none of preferred backends worked, try default CAP_ANY
        try:
            logger.info("Trying fallback default CAP_ANY", device_id=device_id)
            cap = cv2.VideoCapture(device_id, cv2.CAP_ANY)
            if cap.isOpened():
                self._cap = cap
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, self.config.get("camera", {}).get("fps_target", 30))
                logger.info("Camera connected with CAP_ANY", device=device_id)
                self._backoff_idx = 0
                return
        except Exception as e:
            logger.debug("Failed CAP_ANY fallback", error=str(e))

        raise RuntimeError(f"Cannot open camera device {device_id} with any backend")

    def _capture_loop(self) -> None:
        shm = shared_memory.SharedMemory(name=self.shm_name)
        frame_buf = np.ndarray((FRAME_HEIGHT, FRAME_WIDTH, FRAME_CHANNELS), dtype=np.uint8, buffer=shm.buf)
        watchdog_timeout = self.config.get("camera", {}).get("watchdog_timeout_ms", 2000) / 1000.0
        last_frame_time = time.monotonic()

        while self._running and self._cap is not None:
            ret, frame = self._cap.read()
            if not ret:
                if time.monotonic() - last_frame_time > watchdog_timeout:
                    logger.warning("Camera watchdog timeout triggered (no frame received)")
                    raise RuntimeError("Camera frame timeout")
                time.sleep(0.001)
                continue

            last_frame_time = time.monotonic()

            # Preprocessing: resize, BGR->RGB, horizontal mirror
            if frame.shape[0] != FRAME_HEIGHT or frame.shape[1] != FRAME_WIDTH:
                frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.flip(frame, 1)  # Mirror

            # Write to SharedMemory (newest overwrites)
            np.copyto(frame_buf, frame)

        shm.close()

    def _disconnect(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug("Error releasing camera device", error=str(e))
            self._cap = None

    def _backoff_reconnect(self) -> None:
        if not self._running:
            return
        wait = self._backoff_times[min(self._backoff_idx, len(self._backoff_times) - 1)] / 1000.0
        logger.info("Reconnecting camera with backoff", wait_sec=wait)
        time.sleep(wait)
        self._backoff_idx = min(self._backoff_idx + 1, len(self._backoff_times) - 1)

    def stop(self) -> None:
        self._running = False
        self._disconnect()


def start_camera_process(config: dict[str, Any], shm_name: str) -> mp.Process:
    """Spawn camera capture as a separate process."""
    stream = CameraStream(config, shm_name)
    process = mp.Process(target=stream.run, daemon=True, name="camera_capture")
    process.start()
    return process
