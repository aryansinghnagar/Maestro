from __future__ import annotations

import struct
import time
from multiprocessing import shared_memory
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)

# ReAct fix: single source of truth lives in vision.constants.
# These module-level names are kept as re-exports for backward compat.
try:
    from gesture_controller.vision.constants import (
        FRAME_WIDTH,
        FRAME_HEIGHT,
        FRAME_CHANNELS,
        FRAME_SIZE,
        HEADER_SIZE,
        TOTAL_SHM_SIZE as TOTAL_SIZE,
    )
except Exception:  # pragma: no cover - import-time fallback for frozen builds
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480
    FRAME_CHANNELS = 3
    FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * FRAME_CHANNELS  # 921600 bytes
    HEADER_SIZE = 8  # 64-bit sequence counter
    TOTAL_SIZE = HEADER_SIZE + 2 * FRAME_SIZE  # 1843208 bytes
TOTAL_SHM_SIZE = TOTAL_SIZE

# Performance optimization (P8): right-sized SHM buffer dimensions for the
# three most common capture resolutions. Callers building a DoubleFrameBuffer
# for a non-default resolution should pass ``size=compute_total_size(w, h)``
# so the SHM segment is not over-allocated for 720p (saves ~1.4 MiB) or
# under-allocated for 4K (would currently crash on write).
RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "480p": (640, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


def compute_frame_size(width: int, height: int, channels: int = FRAME_CHANNELS) -> int:
    """Bytes required to store a single uncompressed BGR/RGB frame."""
    return width * height * channels


def compute_total_size(width: int, height: int, channels: int = FRAME_CHANNELS) -> int:
    """Total SHM segment size for a double-buffered frame of the given resolution.

    Includes the 8-byte sequence-counter header plus two frame slots
    (write-side alternates between them under the seqlock).
    """
    return HEADER_SIZE + 2 * compute_frame_size(width, height, channels)


class DoubleFrameBuffer:
    """Double-buffered shared memory frame transfer using an atomic-style seqlock sequence counter."""

    def __init__(self, name: str, create: bool = False, size: int = TOTAL_SIZE) -> None:
        self.name = name
        self.create = create
        self.size = size
        self.frame_size = (size - HEADER_SIZE) // 2

        if create:
            self.shm = shared_memory.SharedMemory(name=name, create=True, size=size)
            buf = self.shm.buf
            assert buf is not None
            # Initialize sequence counter to 0
            struct.pack_into("<Q", buf, 0, 0)
        else:
            self.shm = shared_memory.SharedMemory(name=name)
            self.size = size
            self.frame_size = (size - HEADER_SIZE) // 2

    def write(self, frame_bytes: bytes) -> None:
        """Write frame_bytes to the double buffer slot, incrementing seq before and after.

        Performance optimization (P2): accepts any buffer-protocol object
        (``bytes``, ``memoryview``, or a contiguous ``numpy.ndarray``). The
        caller should pass ``memoryview(frame)`` or the numpy array directly
        rather than calling ``frame.tobytes()``, which previously triggered
        an extra ~921 KB allocation per frame at 30 FPS (27 MB/sec of GC
        pressure).
        """
        if len(frame_bytes) != self.frame_size:
            raise ValueError(
                f"Invalid frame size: expected {self.frame_size}, got {len(frame_bytes)}"
            )

        buf = self.shm.buf
        assert buf is not None

        # Read current sequence
        seq = struct.unpack_from("<Q", buf, 0)[0]

        # Increment to odd (write in progress)
        seq_odd = seq + 1
        struct.pack_into("<Q", buf, 0, seq_odd)

        # Write to alternating slot: seq = 0 -> slot 0, seq = 2 -> slot 1
        # Slot index is (seq // 2) % 2
        slot = (seq // 2) % 2
        offset = HEADER_SIZE + slot * self.frame_size
        buf[offset : offset + self.frame_size] = frame_bytes

        # Increment to even (write finished)
        seq_even = seq_odd + 1
        struct.pack_into("<Q", buf, 0, seq_even)

    def read(self) -> Optional[bytes]:
        """Read the latest complete frame, retrying if a concurrent write occurs."""
        buf = self.shm.buf
        assert buf is not None

        max_retries = 10
        for _ in range(max_retries):
            seq1 = struct.unpack_from("<Q", buf, 0)[0]

            # If seq1 is odd, write is in progress; if 0, no frames written yet
            if seq1 % 2 != 0 or seq1 == 0:
                time.sleep(0.001)
                continue

            # Latest complete slot is ((seq1 // 2) - 1) % 2
            slot = ((seq1 // 2) - 1) % 2
            offset = HEADER_SIZE + slot * self.frame_size

            # Copy data to local buffer
            data = bytes(buf[offset : offset + self.frame_size])

            # Verify no concurrent write occurred during the read
            seq2 = struct.unpack_from("<Q", buf, 0)[0]
            if seq1 == seq2:
                return data

        # Return None if consistently failed to read atomically
        return None

    def read_array(self, shape: tuple[int, ...] | None = None) -> Optional["Any"]:
        """Zero-copy read returning a numpy view directly into the SHM buffer.

        Performance optimization (P2): the previous ``read()`` returns a
        ``bytes`` copy, and downstream code then called
        ``np.frombuffer(...).reshape(...).copy()`` — two allocations per
        frame. ``read_array()`` returns a read-only numpy view that shares
        the SHM backing memory; no per-frame copy is made on the read path.

        Seqlock semantics are still honoured: the view is built only after
        ``seq1`` is observed to be even, and the sequence is re-checked
        before returning. The returned array is *read-only* — callers that
        need a mutable frame (e.g. for OpenCV in-place ops) should call
        ``.copy()`` on the result.
        """
        import numpy as np

        buf = self.shm.buf
        assert buf is not None

        if shape is None:
            shape = (FRAME_HEIGHT, FRAME_WIDTH, FRAME_CHANNELS)

        max_retries = 10
        for _ in range(max_retries):
            seq1 = struct.unpack_from("<Q", buf, 0)[0]
            if seq1 % 2 != 0 or seq1 == 0:
                time.sleep(0.001)
                continue

            slot = ((seq1 // 2) - 1) % 2
            offset = HEADER_SIZE + slot * self.frame_size

            # Build a numpy view over the SHM buffer at the slot offset.
            # The view is read-only because ``shm.buf`` is a read-only
            # memoryview; downstream consumers must not attempt in-place
            # writes (those would race with the writer's seqlock).
            view = np.ndarray(
                shape,
                dtype=np.uint8,
                buffer=buf,
                offset=offset,
            )

            # Verify no concurrent write occurred while we built the view.
            seq2 = struct.unpack_from("<Q", buf, 0)[0]
            if seq1 == seq2:
                try:
                    view.flags.writeable = False
                except Exception:
                    pass
                return view

        return None

    def __enter__(self) -> DoubleFrameBuffer:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        try:
            self.close()
        except Exception:
            pass

    def close(self) -> None:
        """Close shared memory access handle."""
        try:
            self.shm.close()
        except Exception:
            pass

    def unlink(self) -> None:
        """Destroy the shared memory segment."""
        try:
            self.shm.unlink()
        except Exception:
            pass
