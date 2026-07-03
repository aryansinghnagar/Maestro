import os
import json
import re
import platform
import structlog
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSlider, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import pyqtSignal, Qt, QRect
from PyQt6.QtGui import QFont

from gesture_controller.gui.gesture_recorder import GestureRecorder
from gesture_controller.core.config_manager import ConfigManager, USER_CONFIG_DIRS

logger = structlog.get_logger(__name__)

class HotkeyCaptureWidget(QPushButton):
    """Button that captures the next key combination pressed."""
    hotkey_captured = pyqtSignal(str)

    def __init__(self, current_hotkey: str = "", parent=None) -> None:
        super().__init__(current_hotkey or "Click to capture...", parent)
        self._capturing = False
        self._modifiers = []
        self.clicked.connect(self._start_capture)
        self.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #fff;
                border: 1px solid #555;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton:focus {
                border-color: #00ffcc;
            }
        """)

    def _start_capture(self) -> None:
        self._capturing = True
        self.setText("Press key combination...")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def keyPressEvent(self, event) -> None:
        if not self._capturing:
            return super().keyPressEvent(event)
            
        self._modifiers = []
        mod_mask = event.modifiers()
        
        if mod_mask & Qt.KeyboardModifier.ControlModifier:
            self._modifiers.append("Ctrl")
        if mod_mask & Qt.KeyboardModifier.ShiftModifier:
            self._modifiers.append("Shift")
        if mod_mask & Qt.KeyboardModifier.AltModifier:
            self._modifiers.append("Alt")
        if mod_mask & Qt.KeyboardModifier.MetaModifier:
            self._modifiers.append("Super")
            
        # Extract base key
        key_code = event.key()
        # Map key codes to strings if possible, otherwise use character text
        if key_code == Qt.Key.Key_Space:
            key_str = "Space"
        elif key_code == Qt.Key.Key_Escape:
            key_str = "Esc"
        elif key_code == Qt.Key.Key_Return:
            key_str = "Enter"
        elif key_code == Qt.Key.Key_Tab:
            key_str = "Tab"
        elif key_code >= Qt.Key.Key_F1 and key_code <= Qt.Key.Key_F12:
            key_str = f"F{key_code - Qt.Key.Key_F1 + 1}"
        else:
            key_str = event.text().upper()
            if not key_str:
                # If key string is empty (e.g. only modifiers were pressed), do not save yet
                return

        hotkey = "+".join(self._modifiers + [key_str])
        self.setText(hotkey)
        self._capturing = False
        self.hotkey_captured.emit(hotkey)

class SettingsWindow(QDialog):
    """Settings dialog managing core configuration properties, profiles and custom gestures."""
    config_changed = pyqtSignal(dict)

    def __init__(self, config_manager: ConfigManager, landmark_callback=None,
                 template_dir: Path | None = None, reload_callback=None, parent=None) -> None:
        super().__init__(parent)
        self._config = config_manager
        self._landmark_callback = landmark_callback
        self._template_dir = template_dir
        self._reload_callback = reload_callback
        self._setup_ui()
        self._load_current_config()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #333;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background: #2e2e2e;
                color: #b0b0b0;
                padding: 10px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                color: #00ffcc;
                border-bottom: 2px solid #00ffcc;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit, QComboBox {
                background-color: #2e2e2e;
                border: 1px solid #444;
                color: #fff;
                padding: 4px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #00ffcc;
                color: #121212;
                font-weight: bold;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #00ddbb;
            }
            QPushButton:disabled {
                background-color: #444;
                color: #888;
            }
        """)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        
        # 1. General Tab
        self._tab_general = QWidget()
        self._setup_general_tab()
        self._tabs.addTab(self._tab_general, "General")
        
        # 2. Sensitivity Tab
        self._tab_sensitivity = QWidget()
        self._setup_sensitivity_tab()
        self._tabs.addTab(self._tab_sensitivity, "Sensitivity")

        # 3. Gestures Tab
        self._tab_gestures = QWidget()
        self._setup_gestures_tab()
        self._tabs.addTab(self._tab_gestures, "Gestures")

        # 4. HUD Tab
        self._tab_hud = QWidget()
        self._setup_hud_tab()
        self._tabs.addTab(self._tab_hud, "HUD")

        layout.addWidget(self._tabs)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._save_btn = QPushButton("Save && Apply")
        self._save_btn.clicked.connect(self._on_apply)
        
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #fff;
                border: 1px solid #555;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        self._cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

    def _setup_general_tab(self) -> None:
        layout = QVBoxLayout(self._tab_general)
        
        # Camera device selection
        cam_layout = QHBoxLayout()
        cam_layout.addWidget(QLabel("Camera Device ID:"))
        self._camera_device = QComboBox()
        for i in range(4):
            self._camera_device.addItem(f"Camera {i}", i)
        cam_layout.addWidget(self._camera_device)
        layout.addLayout(cam_layout)

        # Resolution dropdown
        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Target Resolution:"))
        self._camera_res = QComboBox()
        self._camera_res.addItem("640x480", "640x480")
        self._camera_res.addItem("1280x720", "1280x720")
        res_layout.addWidget(self._camera_res)
        layout.addLayout(res_layout)

        # Auto-reconnect
        self._auto_reconnect = QCheckBox("Auto-reconnect Camera")
        layout.addWidget(self._auto_reconnect)

        # Pause hotkey
        hotkey_layout = QHBoxLayout()
        hotkey_layout.addWidget(QLabel("Pause/Resume Hotkey:"))
        self._hotkey_widget = HotkeyCaptureWidget()
        hotkey_layout.addWidget(self._hotkey_widget)
        layout.addLayout(hotkey_layout)
        
        layout.addStretch()

    def _setup_sensitivity_tab(self) -> None:
        layout = QVBoxLayout(self._tab_sensitivity)
        
        # Global multiplier
        layout.addWidget(QLabel("Global Sensitivity Multiplier:"))
        self._sens_slider = QSlider(Qt.Orientation.Horizontal)
        self._sens_slider.setRange(10, 300)  # 0.1 - 3.0
        self._sens_slider.setValue(100)
        self._sens_label = QLabel("1.00")
        self._sens_slider.valueChanged.connect(
            lambda v: self._sens_label.setText(f"{v/100:.2f}")
        )
        
        sens_row = QHBoxLayout()
        sens_row.addWidget(self._sens_slider)
        sens_row.addWidget(self._sens_label)
        layout.addLayout(sens_row)
        
        # Filter cutoff
        layout.addWidget(QLabel("One-Euro Filter Min Cutoff:"))
        self._cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self._cutoff_slider.setRange(1, 100)  # 0.1 - 10.0
        self._cutoff_slider.setValue(10)
        self._cutoff_label = QLabel("1.0")
        self._cutoff_slider.valueChanged.connect(
            lambda v: self._cutoff_label.setText(f"{v/10:.1f}")
        )
        
        cutoff_row = QHBoxLayout()
        cutoff_row.addWidget(self._cutoff_slider)
        cutoff_row.addWidget(self._cutoff_label)
        layout.addLayout(cutoff_row)

        layout.addStretch()

    def _setup_gestures_tab(self) -> None:
        layout = QVBoxLayout(self._tab_gestures)
        
        # Custom templates trigger button
        self._record_btn = QPushButton("Record Custom Gesture...")
        self._record_btn.clicked.connect(self._on_record_gesture)
        layout.addWidget(self._record_btn)

        # Gestures Tree
        self._gestures_tree = QTreeWidget()
        self._gestures_tree.setHeaderLabels(["Gesture", "Type", "Default Action"])
        self._gestures_tree.setStyleSheet("background-color: #2e2e2e; border: 1px solid #444; color: #fff;")
        layout.addWidget(self._gestures_tree)

    def _setup_hud_tab(self) -> None:
        layout = QVBoxLayout(self._tab_hud)
        
        self._hud_enabled = QCheckBox("Enable Transparent HUD Overlay")
        layout.addWidget(self._hud_enabled)
        
        # Opacity
        layout.addWidget(QLabel("HUD Opacity:"))
        self._hud_opacity = QSlider(Qt.Orientation.Horizontal)
        self._hud_opacity.setRange(10, 100)
        self._hud_opacity.setValue(80)
        self._hud_opacity_label = QLabel("0.80")
        self._hud_opacity.valueChanged.connect(
            lambda v: self._hud_opacity_label.setText(f"{v/100:.2f}")
        )
        
        op_row = QHBoxLayout()
        op_row.addWidget(self._hud_opacity)
        op_row.addWidget(self._hud_opacity_label)
        layout.addLayout(op_row)

        self._show_points = QCheckBox("Show Joint Tracking Dots")
        layout.addWidget(self._show_points)
        
        self._show_ring = QCheckBox("Show Gesture Progress Ring")
        layout.addWidget(self._show_ring)
        
        layout.addStretch()

    def _load_current_config(self) -> None:
        """Populate current GUI settings from ConfigManager values."""
        self._camera_device.setCurrentIndex(self._config.get("camera.device_id", 0))
        
        # Load sensitivity
        sens = int(self._config.get("sensitivity.global_multiplier", 1.0) * 100)
        self._sens_slider.setValue(sens)
        
        cutoff = int(self._config.get("filter.one_euro.min_cutoff", 1.0) * 10)
        self._cutoff_slider.setValue(cutoff)
        
        # Load HUD settings
        self._hud_enabled.setChecked(self._config.get("hud.enabled", True))
        opacity = int(self._config.get("hud.opacity", 0.8) * 100)
        self._hud_opacity.setValue(opacity)
        self._show_points.setChecked(self._config.get("hud.show_tracking_points", True))
        self._show_ring.setChecked(self._config.get("hud.show_progress_ring", True))
        
        # Load hotkey
        self._hotkey_widget.setText(self._config.get("pause_hotkey", "Ctrl+Alt+P"))

        # Populate predefined gestures list
        self._gestures_tree.clear()
        gestures_yaml_path = self._config._config.get("gestures", [])
        for g in gestures_yaml_path:
            name = g.get("name", "Unknown")
            g_type = g.get("type", "static")
            action = "None"
            # Extract trigger state action
            for state in g.get("states", []):
                if state.get("is_terminal") or state.get("id") == "Trigger":
                    action = state.get("action", "None")
                    break
            item = QTreeWidgetItem([name, g_type, action])
            self._gestures_tree.addTopLevelItem(item)

    def _on_record_gesture(self) -> None:
        """Launch the QDialog GestureRecorder."""
        recorder = GestureRecorder(parent=self, landmark_callback=self._landmark_callback)
        recorder.recording_complete.connect(self._on_custom_gesture_recorded)
        recorder.exec()

    def _sanitize_gesture_name(self, name: str) -> str | None:
        """Return a safe filename stem, or None if invalid."""
        if not name or not name.strip():
            return None
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
            return None
        return name

    def _on_custom_gesture_recorded(self, template_data: dict) -> None:
        """Save new template to template directory."""
        name = self._sanitize_gesture_name(template_data.get("name", ""))
        if name is None:
            QMessageBox.critical(
                self, "Invalid Gesture Name",
                "Gesture name must be 1-64 characters: alphanumeric, dash, or underscore only."
            )
            return

        if self._template_dir is None:
            QMessageBox.critical(
                self, "Cannot Save Gesture",
                "The gesture engine is not connected. Cannot save custom gestures."
            )
            return

        dest_path = self._template_dir / f"{name}.json"
        
        # Defense-in-depth: verify the resolved path is still inside template_dir
        try:
            dest_path.resolve().relative_to(self._template_dir.resolve())
        except ValueError:
            QMessageBox.critical(self, "Security Error", "Resolved path escapes template directory.")
            return

        try:
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2)
            QMessageBox.information(self, "Gesture Saved", f"Custom gesture '{name}' saved successfully!")
            
            # Reload matcher templates
            if self._reload_callback is not None:
                self._reload_callback(self._template_dir)
            elif self._landmark_callback is not None and hasattr(self._landmark_callback, "__self__"):
                self._landmark_callback.__self__._custom_matcher.load_templates(self._template_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error Saving Gesture", f"Failed to write template: {e}")

    def _on_apply(self) -> None:
        """Save settings updates back to ConfigManager."""
        self._config.set("camera.device_id", self._camera_device.currentIndex())
        self._config.set("sensitivity.global_multiplier", self._sens_slider.value() / 100.0)
        self._config.set("filter.one_euro.min_cutoff", self._cutoff_slider.value() / 10.0)
        
        self._config.set("hud.enabled", self._hud_enabled.isChecked())
        self._config.set("hud.opacity", self._hud_opacity.value() / 100.0)
        self._config.set("hud.show_tracking_points", self._show_points.isChecked())
        self._config.set("hud.show_progress_ring", self._show_ring.isChecked())
        
        self._config.set("pause_hotkey", self._hotkey_widget.text())

        # Save to config.yaml file
        sys_name = platform.system()
        # Find user folder
        user_dir = USER_CONFIG_DIRS.get(sys_name)
        if user_dir:
            try:
                user_dir.mkdir(parents=True, exist_ok=True)
                # Write back current config dictionary
                import yaml
                with open(user_dir / "config.yaml", "w", encoding="utf-8") as f:
                    yaml.safe_dump(self._config._config, f)
                logger.info("Configuration saved successfully to user profile config.yaml")
            except Exception as e:
                logger.error("Failed saving configuration overrides to file", error=str(e))
                
        # Emit signal to alert engine components
        self.config_changed.emit(self._config._config)
        self.accept()
