import struct
import time
from multiprocessing import shared_memory
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_CHANNELS = 3
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * FRAME_CHANNELS  # 921600 bytes
HEADER_SIZE = 8  # 64-bit sequence counter
TOTAL_SIZE = HEADER_SIZE + 2 * FRAME_SIZE  # 1843208 bytes


class DoubleFrameBuffer:
    """Double-buffered shared memory frame transfer using an atomic-style seqlock sequence counter."""

    def __init__(self, name: str, create: bool = False, size: int = TOTAL_SIZE) -> None:
        self.name = name
        self.create = create
        self.size = size

        if create:
            self.shm = shared_memory.SharedMemory(name=name, create=True, size=size)
            buf = self.shm.buf
            assert buf is not None
            # Initialize sequence counter to 0
            struct.pack_into("<Q", buf, 0, 0)
        else:
            self.shm = shared_memory.SharedMemory(name=name)

    def write(self, frame_bytes: bytes) -> None:
        """Write frame_bytes to the double buffer slot, incrementing seq before and after."""
        if len(frame_bytes) != FRAME_SIZE:
            raise ValueError(f"Invalid frame size: expected {FRAME_SIZE}, got {len(frame_bytes)}")

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
        offset = HEADER_SIZE + slot * FRAME_SIZE
        buf[offset : offset + FRAME_SIZE] = frame_bytes

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
            offset = HEADER_SIZE + slot * FRAME_SIZE

            # Copy data to local buffer
            data = bytes(buf[offset : offset + FRAME_SIZE])

            # Verify no concurrent write occurred during the read
            seq2 = struct.unpack_from("<Q", buf, 0)[0]
            if seq1 == seq2:
                return data

        # Return None if consistently failed to read atomically
        return None

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
