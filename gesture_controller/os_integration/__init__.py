import sys
import platform
import structlog
from gesture_controller.os_integration.base_controller import BaseController

logger = structlog.get_logger(__name__)

def create_controller() -> BaseController:
    """Factory function that returns the correct platform controller."""
    system = platform.system()
    
    if system == "Windows":
        from gesture_controller.os_integration.windows_controller import WindowsController
        ctrl = WindowsController()
        if ctrl.is_supported():
            logger.info("Created WindowsController OS adapter")
            return ctrl
            
    elif system == "Darwin":
        from gesture_controller.os_integration.macos_controller import MacOSController
        ctrl = MacOSController()
        if ctrl.is_supported():
            logger.info("Created MacOSController OS adapter")
            return ctrl
            
    elif system == "Linux":
        from gesture_controller.os_integration.linux_wayland_controller import LinuxWaylandController
        ctrl = LinuxWaylandController()
        if ctrl.is_supported():
            logger.info("Created LinuxWaylandController OS adapter")
            return ctrl

    # Fallback to raising RuntimeError if no supported controller
    raise RuntimeError(f"No supported OS controller found for platform: {system}")
