import pytest
import platform
from gesture_controller.os_integration import create_controller


@pytest.mark.requires_hardware
def test_hardware_in_loop_controller_simulation() -> None:
    """Verifies native controller execution directly on host hardware (S4-3)."""
    sys_name = platform.system()

    # Instantiate the platform controller
    controller = create_controller()

    # Assert that the native controller is supported on this platform
    assert (
        controller.is_supported() is True
    ), f"Native controller is not supported on host OS: {sys_name}"

    # Simulate a safe, non-destructive keyboard press (Shift key)
    try:
        controller.key_press("Shift")
        controller.key_release("Shift")
    except Exception as e:
        pytest.fail(f"Native input simulation failed on {sys_name} hardware: {e}")
