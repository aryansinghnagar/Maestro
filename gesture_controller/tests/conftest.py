import pytest
import numpy as np
from multiprocessing import shared_memory
from gesture_controller.models.data_types import Hand, Landmark3D

def pytest_configure(config) -> None:
    """Configure settings if needed."""
    pass

def pytest_unconfigure(config) -> None:
    """Clean up on teardown."""
    pass

def make_hand(landmarks: list[tuple[float, float, float]], handedness: str = "Right") -> Hand:
    """Helper to construct a Hand object from coordinate tuples."""
    lms = tuple(Landmark3D(x=x, y=y, z=z) for x, y, z in landmarks)
    return Hand(landmarks=lms, handedness=handedness, confidence=1.0)

@pytest.fixture
def open_palm_hand() -> Hand:
    """Hand with all 5 fingers extended, facing camera."""
    coords = [
        (0.5, 0.8, 0.0),   # 0: WRIST
        (0.45, 0.65, 0.0),  # 1: THUMB_CMC
        (0.4, 0.5, 0.0),    # 2: THUMB_MCP
        (0.37, 0.4, 0.0),   # 3: THUMB_IP
        (0.35, 0.3, 0.0),   # 4: THUMB_TIP
        (0.42, 0.55, 0.0),  # 5: INDEX_MCP
        (0.4, 0.4, 0.0),    # 6: INDEX_PIP
        (0.39, 0.3, 0.0),   # 7: INDEX_DIP
        (0.38, 0.22, 0.0),  # 8: INDEX_TIP
        (0.5, 0.53, 0.0),   # 9: MIDDLE_MCP
        (0.5, 0.38, 0.0),   # 10: MIDDLE_PIP
        (0.5, 0.28, 0.0),   # 11: MIDDLE_DIP
        (0.5, 0.2, 0.0),    # 12: MIDDLE_TIP
        (0.57, 0.55, 0.0),  # 13: RING_MCP
        (0.58, 0.42, 0.0),  # 14: RING_PIP
        (0.58, 0.33, 0.0),  # 15: RING_DIP
        (0.58, 0.26, 0.0),  # 16: RING_TIP
        (0.63, 0.58, 0.0),  # 17: PINKY_MCP
        (0.64, 0.47, 0.0),  # 18: PINKY_PIP
        (0.64, 0.39, 0.0),  # 19: PINKY_DIP
        (0.65, 0.33, 0.0),  # 20: PINKY_TIP
    ]
    return make_hand(coords)

@pytest.fixture
def pointing_hand() -> Hand:
    """Index finger extended, all others curled."""
    coords = [
        (0.5, 0.8, 0.0),   # 0: WRIST
        (0.45, 0.65, -0.02), # 1: THUMB_CMC
        (0.47, 0.7, -0.01),  # 2: THUMB_MCP
        (0.48, 0.73, -0.01), # 3: THUMB_IP
        (0.47, 0.7, -0.01),  # 4: THUMB_TIP
        (0.44, 0.6, 0.0),   # 5: INDEX_MCP
        (0.43, 0.45, 0.0),  # 6: INDEX_PIP
        (0.42, 0.33, 0.0),  # 7: INDEX_DIP
        (0.41, 0.22, 0.0),  # 8: INDEX_TIP
        (0.5, 0.62, 0.0),   # 9: MIDDLE_MCP
        (0.51, 0.68, 0.0),  # 10: MIDDLE_PIP
        (0.51, 0.72, 0.0),  # 11: MIDDLE_DIP
        (0.50, 0.7, 0.0),   # 12: MIDDLE_TIP
        (0.55, 0.63, 0.0),  # 13: RING_MCP
        (0.56, 0.68, 0.0),  # 14: RING_PIP
        (0.56, 0.72, 0.0),  # 15: RING_DIP
        (0.55, 0.7, 0.0),   # 16: RING_TIP
        (0.59, 0.64, 0.0),  # 17: PINKY_MCP
        (0.60, 0.68, 0.0),  # 18: PINKY_PIP
        (0.60, 0.71, 0.0),  # 19: PINKY_DIP
        (0.59, 0.69, 0.0),  # 20: PINKY_TIP
    ]
    return make_hand(coords)

@pytest.fixture
def fist_hand() -> Hand:
    """All fingers curled (closed fist)."""
    coords = [
        (0.5, 0.8, 0.0),
        (0.45, 0.68, -0.03), (0.47, 0.72, -0.02), (0.48, 0.74, -0.02), (0.47, 0.72, -0.02),
        (0.46, 0.68, 0.0), (0.47, 0.72, 0.0), (0.47, 0.74, 0.0), (0.46, 0.72, 0.0),
        (0.50, 0.68, 0.0), (0.50, 0.72, 0.0), (0.50, 0.74, 0.0), (0.50, 0.72, 0.0),
        (0.53, 0.68, 0.0), (0.54, 0.72, 0.0), (0.54, 0.74, 0.0), (0.53, 0.72, 0.0),
        (0.56, 0.69, 0.0), (0.57, 0.72, 0.0), (0.57, 0.74, 0.0), (0.56, 0.72, 0.0),
    ]
    return make_hand(coords)

@pytest.fixture
def pinch_hand() -> Hand:
    """Thumb and index tips close together, others extended."""
    coords = [
        (0.5, 0.8, 0.0),
        (0.45, 0.65, -0.02), (0.42, 0.5, -0.02), (0.40, 0.38, -0.02), (0.39, 0.32, -0.02),
        (0.44, 0.6, 0.0), (0.42, 0.45, 0.0), (0.41, 0.35, 0.0), (0.40, 0.32, 0.0),
        (0.5, 0.58, 0.0), (0.5, 0.43, 0.0), (0.5, 0.32, 0.0), (0.5, 0.24, 0.0),
        (0.56, 0.59, 0.0), (0.57, 0.46, 0.0), (0.57, 0.36, 0.0), (0.57, 0.28, 0.0),
        (0.60, 0.61, 0.0), (0.61, 0.50, 0.0), (0.61, 0.42, 0.0), (0.61, 0.36, 0.0),
    ]
    return make_hand(coords)

@pytest.fixture
def thumbs_up_hand() -> Hand:
    """Thumb extended up, all others curled."""
    coords = [
        (0.5, 0.8, 0.0),
        (0.42, 0.65, -0.04), (0.35, 0.50, -0.04), (0.30, 0.38, -0.04), (0.27, 0.28, -0.04),
        (0.46, 0.68, 0.0), (0.47, 0.72, 0.0), (0.47, 0.74, 0.0), (0.46, 0.72, 0.0),
        (0.50, 0.68, 0.0), (0.50, 0.72, 0.0), (0.50, 0.74, 0.0), (0.50, 0.72, 0.0),
        (0.53, 0.68, 0.0), (0.54, 0.72, 0.0), (0.54, 0.74, 0.0), (0.53, 0.72, 0.0),
        (0.56, 0.69, 0.0), (0.57, 0.72, 0.0), (0.57, 0.74, 0.0), (0.56, 0.72, 0.0),
    ]
    return make_hand(coords)

@pytest.fixture
def shared_memory_frame() -> tuple[shared_memory.SharedMemory, np.ndarray]:
    """Provides a shared memory segment populated with a dummy frame."""
    shm = shared_memory.SharedMemory(create=True, size=640*480*3)
    frame = np.ndarray((480, 640, 3), dtype=np.uint8, buffer=shm.buf)
    frame.fill(0)
    yield shm, frame
    shm.close()
    shm.unlink()

@pytest.fixture(scope="session")
def qapp() -> "QApplication":
    """Provide a session-scoped QApplication instance for all GUI tests."""
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    app.processEvents()
