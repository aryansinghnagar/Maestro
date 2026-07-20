from gesture_controller.os_integration.keycodes import (
    normalize_key,
    normalize_key_combo,
    get_linux_keycode,
    get_windows_vkcode,
    get_mac_keycode,
)


def test_normalize_key() -> None:
    assert normalize_key("Win") == "super"
    assert normalize_key("Control") == "ctrl"
    assert normalize_key("a") == "a"


def test_normalize_key_combo() -> None:
    assert normalize_key_combo(["Control", "Win", "A"]) == ["ctrl", "super", "a"]


def test_get_keycodes() -> None:
    # Linux
    assert get_linux_keycode("esc") == 1
    assert get_linux_keycode("unknown") == 0

    # Windows
    assert get_windows_vkcode("shift") == 0x10
    assert get_windows_vkcode("a") == 0x41
    assert get_windows_vkcode("unknown") == 0

    # macOS
    assert get_mac_keycode("a") == 0x00
