"""Theme detection and QSS application for accessibility support."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QColor, QPalette
from PyQt6.QtWidgets import QApplication

# Okabe-Ito color-blind safe palette
OKABE_ITO = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "bluish_green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermilion": "#D55E00",
    "reddish_purple": "#CC79A7",
}

_DARK_QSS = f"""
QWidget {{
    background-color: #121212;
    color: #e0e0e0;
    font-size: 14px;
}}

QPushButton {{
    background-color: #2e2e2e;
    border: 1px solid #444;
    color: #fff;
    padding: 8px 16px;
    border-radius: 4px;
}}

QPushButton:hover {{
    background-color: #3e3e3e;
    border: 1px solid {OKABE_ITO['sky_blue']};
}}

QPushButton:focus {{
    outline: 2px solid {OKABE_ITO['sky_blue']};
    border: 2px solid {OKABE_ITO['sky_blue']};
}}

QLineEdit, QComboBox, QSpinBox {{
    background-color: #2e2e2e;
    border: 1px solid #444;
    color: #fff;
    padding: 4px;
    border-radius: 4px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {OKABE_ITO['sky_blue']};
}}

QTabBar::tab {{
    background: #2e2e2e;
    color: #b0b0b0;
    padding: 10px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background: #1e1e1e;
    color: {OKABE_ITO['sky_blue']};
    border-bottom: 2px solid {OKABE_ITO['sky_blue']};
}}
"""

_LIGHT_QSS = f"""
QWidget {{
    background-color: #f5f5f5;
    color: #333333;
    font-size: 14px;
}}

QPushButton {{
    background-color: #ffffff;
    border: 1px solid #ccc;
    color: #333;
    padding: 8px 16px;
    border-radius: 4px;
}}

QPushButton:hover {{
    background-color: #e8e8e8;
    border: 1px solid {OKABE_ITO['blue']};
}}

QPushButton:focus {{
    outline: 2px solid {OKABE_ITO['blue']};
    border: 2px solid {OKABE_ITO['blue']};
}}

QLineEdit, QComboBox, QSpinBox {{
    background-color: #ffffff;
    border: 1px solid #ccc;
    color: #333;
    padding: 4px;
    border-radius: 4px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {OKABE_ITO['blue']};
}}

QTabBar::tab {{
    background: #e0e0e0;
    color: #555555;
    padding: 10px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background: #ffffff;
    color: {OKABE_ITO['blue']};
    border-bottom: 2px solid {OKABE_ITO['blue']};
}}
"""

_HIGH_CONTRAST_QSS = f"""
QWidget {{
    background-color: #000000;
    color: #ffffff;
    font-size: 16px;
    font-weight: bold;
}}

QPushButton {{
    background-color: #000000;
    color: #ffff00;
    border: 2px solid #ffff00;
    padding: 8px 16px;
}}

QPushButton:hover {{
    background-color: #222000;
    border: 2px solid #ffffff;
}}

QPushButton:focus {{
    outline: 4px solid #00ffff;
    border: 4px solid #00ffff;
}}

QLineEdit, QComboBox, QSpinBox {{
    background-color: #000000;
    color: #ffffff;
    border: 2px solid #ffffff;
    padding: 6px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 3px solid #ffff00;
}}

QTabBar::tab {{
    background: #000000;
    color: #ffffff;
    border: 2px solid #ffffff;
    padding: 10px;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    color: #ffff00;
    border: 3px solid #ffff00;
}}
"""


def detect_system_theme() -> str:
    """Detect system color scheme.

    Returns: "light", "dark", or "high-contrast"
    """
    if hasattr(QGuiApplication, "styleHints"):
        color_scheme = QGuiApplication.styleHints().colorScheme()
        if color_scheme == Qt.ColorScheme.Dark:
            return "dark"
        elif color_scheme == Qt.ColorScheme.Light:
            return "light"

    # Fallback: check palette lightness
    palette = QGuiApplication.palette()
    bg = palette.color(QPalette.ColorRole.Window)
    if bg.lightness() < 128:
        return "dark"
    return "light"


def apply_theme(theme: str) -> None:
    """Apply a theme to the application."""
    app = QApplication.instance()
    if not app:
        return

    if theme == "auto":
        theme = detect_system_theme()

    if theme == "dark":
        app.setStyleSheet(_DARK_QSS)
    elif theme == "light":
        app.setStyleSheet(_LIGHT_QSS)
    elif theme == "high-contrast":
        app.setStyleSheet(_HIGH_CONTRAST_QSS)

    # Propagate high contrast property down to children if needed
    for widget in app.allWidgets():
        widget.setProperty("highContrast", "true" if theme == "high-contrast" else "false")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


def detect_reduced_motion() -> bool:
    """Detect if user prefers reduced motion."""
    import platform

    system = platform.system()

    if system == "Darwin":
        try:
            import Cocoa

            return Cocoa.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion()
        except ImportError:
            return False

    elif system == "Windows":
        try:
            import ctypes

            # SPI_GETCLIENTAREAANIMATION = 0x1042
            result = ctypes.c_int(0)
            ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(result), 0)
            return not result.value  # If animation disabled, prefer reduced motion
        except Exception:
            return False

    # Linux: check GTK setting or fallback to GNOME
    return False
