import pytest
from gesture_controller.vision.double_buffer import (
    DoubleFrameBuffer,
    FRAME_SIZE,
    TOTAL_SIZE,
)


def test_double_buffer_write_read() -> None:
    shm_name = "test_shm_write_read"
    writer = DoubleFrameBuffer(shm_name, create=True)
    reader = DoubleFrameBuffer(shm_name, create=False)

    try:
        frame1 = b"\x01" * FRAME_SIZE
        writer.write(frame1)

        read_frame = reader.read()
        assert read_frame == frame1
    finally:
        writer.close()
        writer.unlink()
        reader.close()


def test_double_buffer_latest_frame() -> None:
    shm_name = "test_shm_latest_frame"
    writer = DoubleFrameBuffer(shm_name, create=True)
    reader = DoubleFrameBuffer(shm_name, create=False)

    try:
        frame1 = b"\x01" * FRAME_SIZE
        frame2 = b"\x02" * FRAME_SIZE
        frame3 = b"\x03" * FRAME_SIZE

        writer.write(frame1)
        writer.write(frame2)
        assert reader.read() == frame2

        writer.write(frame3)
        assert reader.read() == frame3
    finally:
        writer.close()
        writer.unlink()
        reader.close()


def test_double_buffer_empty() -> None:
    shm_name = "test_shm_empty"
    writer = DoubleFrameBuffer(shm_name, create=True)
    reader = DoubleFrameBuffer(shm_name, create=False)

    try:
        # No frames written yet
        assert reader.read() is None
    finally:
        writer.close()
        writer.unlink()
        reader.close()


def test_double_buffer_invalid_size() -> None:
    shm_name = "test_shm_invalid_size"
    writer = DoubleFrameBuffer(shm_name, create=True)

    try:
        with pytest.raises(ValueError):
            writer.write(b"\x01" * 10)
    finally:
        writer.close()
        writer.unlink()
