import multiprocessing as mp
import platform
import time
import uuid
from pathlib import Path
from typing import Any
import structlog

from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.vision.double_buffer import DoubleFrameBuffer, TOTAL_SIZE
from gesture_controller.core.profiler import frame_budget

logger = structlog.get_logger(__name__)


class FramePipeline:
    """Manages the camera process and shared memory lifecycle."""

    def __init__(self, config: ConfigManager, create_camera_process: Any = None) -> None:
        self._config = config
        self._fps_target = config.get("camera.fps_target", 30)
        self._frame_interval = 1.0 / self._fps_target
        self._last_processed = 0.0
        self._processed_count = 0
        self._skip_count = 0
        self._shm_name = f"maestro_shm_{uuid.uuid4().hex}"
        self._frame_size = TOTAL_SIZE
        self._frame_ready_event = mp.Event()
        self._db_buffer: DoubleFrameBuffer | None = None
        self._camera_process: Any = None

        if create_camera_process is None:
            from gesture_controller.vision.camera_stream import create_camera_process as default_create
            self._create_camera_process = default_create
        else:
            self._create_camera_process = create_camera_process

    def start(self) -> None:
        self._db_buffer = DoubleFrameBuffer(self._shm_name, create=True, size=self._frame_size)
        self._shm_name = self._db_buffer.shm.name
        
        # Tighten SharedMemory permissions on Unix (S3-14)
        if platform.system() != "Windows":
            shm_file = Path("/dev/shm") / self._shm_name  # nosec B108
            if shm_file.exists():
                try:
                    shm_file.chmod(0o600)
                    logger.debug("Tightened shared memory file permissions", path=str(shm_file), mode="0600")
                except Exception as e:
                    logger.warning("Failed to chmod shared memory segment", path=str(shm_file), error=str(e))
                    
        self._camera_process = self._create_camera_process(
            self._config._config, self._shm_name, self._frame_ready_event
        )
        logger.info("Camera Stream process spawned", shm_name=self._shm_name)

    def wait_for_frame(self, timeout: float = 0.1) -> bool:
        with frame_budget.measure("wait_for_frame"):
            if self._frame_ready_event and self._frame_ready_event.wait(timeout=timeout):
                self._frame_ready_event.clear()
                return True
        return False

    def should_process(self, timestamp: float) -> bool:
        elapsed = timestamp - self._last_processed
        if elapsed < self._frame_interval:
            self._skip_count += 1
            return False
        self._last_processed = timestamp
        self._processed_count += 1
        return True

    def maybe_idle(self, last_hand_time: float) -> None:
        now = time.monotonic()
        # Drop to 5 FPS when no hands detected for 30s.
        if now - last_hand_time > 30.0 and self._fps_target > 5:
            self._fps_target = 5
            self._frame_interval = 1.0 / 5.0
            logger.info("No hands for 30s, dropping to 5 FPS (power save)")
        elif now - last_hand_time < 1.0 and self._fps_target < 30:
            self._fps_target = 30
            self._frame_interval = 1.0 / 30.0
            logger.info("Hand detected, restoring 30 FPS")

    def adapt_fps(self, processing_time: float) -> None:
        """Adjust FPS target based on processing latency to avoid accumulating backlog."""
        target_interval = 1.0 / self._fps_target
        if processing_time > target_interval * 1.2:
            # Lower FPS
            new_fps = max(15, int(self._fps_target * 0.8))
            if new_fps != self._fps_target:
                logger.warning(
                    "Lowering FPS target to avoid backlog",
                    old_fps=self._fps_target,
                    new_fps=new_fps,
                    latency_ms=processing_time * 1000,
                )
                self._fps_target = new_fps
                self._frame_interval = 1.0 / new_fps
        elif processing_time < target_interval * 0.5 and self._fps_target < 30:
            # Raise FPS back toward 30
            new_fps = min(30, int(self._fps_target * 1.1))
            if new_fps != self._fps_target:
                logger.info(
                    "Raising FPS target back toward default",
                    old_fps=self._fps_target,
                    new_fps=new_fps,
                    latency_ms=processing_time * 1000,
                )
                self._fps_target = new_fps
                self._frame_interval = 1.0 / new_fps

    def shutdown(self) -> None:
        if self._camera_process:
            try:
                self._camera_process.terminate()
                self._camera_process.join(timeout=2.0)
                if self._camera_process.is_alive():
                    self._camera_process.kill()
            except Exception as e:
                logger.warning("Failed to terminate camera process during shutdown", error=str(e))
            self._camera_process = None

        if self._db_buffer:
            try:
                self._db_buffer.close()
                self._db_buffer.shm.unlink()
                logger.info("Shared memory segment cleanly unlinked")
            except Exception as e:
                logger.error("Failed unlinking shared memory segment during shutdown", error=str(e))
            self._db_buffer = None

    @property
    def shm_name(self) -> str:
        return self._shm_name

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def skip_count(self) -> int:
        return self._skip_count

    @property
    def frame_budget_snapshot(self) -> dict:
        """Return per-stage timing stats from FrameTimeBudget."""
        return frame_budget.snapshot()
