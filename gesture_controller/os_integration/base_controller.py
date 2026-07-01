from abc import ABC, abstractmethod

class BaseController(ABC):
    """Abstract base class defining OS action simulation interface."""

    @abstractmethod
    def is_supported(self) -> bool:
        """Return True if this controller is supported on the current platform."""
        pass

    @abstractmethod
    def key_press(self, key: str, modifiers: list[str] | None = None) -> None:
        """Simulate a key press with optional modifier keys."""
        pass

    @abstractmethod
    def key_release(self, key: str) -> None:
        """Release a simulated key."""
        pass

    @abstractmethod
    def key_combo(self, keys: list[str]) -> None:
        """Press a combination of keys (hotkey)."""
        pass

    @abstractmethod
    def mouse_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        """Perform a mouse click at the current position or specified coordinate."""
        pass

    @abstractmethod
    def mouse_double_click(self, button: str = "left", x: int | None = None, y: int | None = None) -> None:
        """Perform a mouse double click."""
        pass

    @abstractmethod
    def mouse_move(self, x: int, y: int, absolute: bool = True) -> None:
        """Move the mouse pointer to a position (absolute or relative)."""
        pass

    @abstractmethod
    def mouse_scroll(self, delta_x: int = 0, delta_y: int = 0) -> None:
        """Scroll the mouse wheel horizontally or vertically."""
        pass

    @abstractmethod
    def get_foreground_app(self) -> str:
        """Get the filename of the active foreground process (lowercase)."""
        pass

    @abstractmethod
    def minimize_active_window(self) -> None:
        """Minimize the active foreground window."""
        pass

    @abstractmethod
    def switch_window(self) -> None:
        """Trigger application/window switching (e.g. Alt+Tab)."""
        pass

    @abstractmethod
    def show_desktop(self) -> None:
        """Show or hide the desktop (minimize all windows)."""
        pass

    @abstractmethod
    def media_play_pause(self) -> None:
        """Simulate media play/pause key."""
        pass

    @abstractmethod
    def media_next(self) -> None:
        """Simulate next track key."""
        pass

    @abstractmethod
    def media_previous(self) -> None:
        """Simulate previous track key."""
        pass

    @abstractmethod
    def media_volume_up(self) -> None:
        """Simulate media volume up."""
        pass

    @abstractmethod
    def media_volume_down(self) -> None:
        """Simulate media volume down."""
        pass
