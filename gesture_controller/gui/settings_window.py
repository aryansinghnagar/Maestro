import os
import json
import re
import platform
import structlog
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSlider,
    QCheckBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from gesture_controller.gui.gesture_recorder import GestureRecorder
from gesture_controller.core.config_manager import ConfigManager
from gesture_controller.core.paths import user_config_dir

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

    def __init__(
        self,
        config_manager: ConfigManager,
        landmark_callback=None,
        template_dir: Path | None = None,
        reload_callback=None,
        parent=None,
    ) -> None:
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

        # Detect system dark/light theme dynamically (S3-17)
        from PyQt6.QtGui import QGuiApplication, QPalette

        is_dark = True
        try:
            from PyQt6.QtCore import Qt

            is_dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except AttributeError:
            bg_color = QGuiApplication.palette().color(QPalette.ColorRole.Window)
            is_dark = (
                (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
            ) < 128

        if is_dark:
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
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                    color: #333333;
                }
                QTabWidget::pane {
                    border: 1px solid #ccc;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background: #e0e0e0;
                    color: #555555;
                    padding: 10px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    min-width: 80px;
                }
                QTabBar::tab:selected {
                    background: #ffffff;
                    color: #0088cc;
                    border-bottom: 2px solid #0088cc;
                }
                QLabel {
                    color: #333333;
                }
                QLineEdit, QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #ccc;
                    color: #333;
                    padding: 4px;
                    border-radius: 4px;
                }
                QPushButton {
                    background-color: #0088cc;
                    color: #ffffff;
                    font-weight: bold;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #006699;
                }
                QPushButton:disabled {
                    background-color: #ddd;
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

        # 5. Accessibility Tab
        self._tab_accessibility = QWidget()
        self._setup_accessibility_tab()
        self._tabs.addTab(self._tab_accessibility, "Accessibility")

        # 6. Plugins Tab
        self._tab_plugins = QWidget()
        self._setup_plugins_tab()
        self._tabs.addTab(self._tab_plugins, "Plugins")

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

        self._camera_device.setAccessibleName("Camera Device Selection")
        self._camera_res.setAccessibleName("Camera Resolution Selection")
        self._auto_reconnect.setAccessibleName("Auto Reconnect Checkbox")
        self._hotkey_widget.setAccessibleName("Pause Resume Hotkey Input")

        # Language selector
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        self._lang_combo = QComboBox()
        self._lang_combo.setAccessibleName("Language selector")
        self._lang_combo.setAccessibleDescription("Select the display language for Maestro.")

        from gesture_controller.core.i18n import available_languages, current_lang

        _LANG_DISPLAY = {
            "en": "English",
            "es": "Español",
            "fr": "Français",
            "de": "Deutsch",
            "ja": "日本語",
            "ar": "العربية",
            "hi": "हिन्दी",
        }
        _cur = current_lang()
        for code in available_languages():
            label = _LANG_DISPLAY.get(code, code.upper())
            self._lang_combo.addItem(label, code)
            if code == _cur:
                self._lang_combo.setCurrentIndex(self._lang_combo.count() - 1)

        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(self._lang_combo)
        layout.addLayout(lang_layout)

        layout.addStretch()

    def _setup_sensitivity_tab(self) -> None:
        layout = QVBoxLayout(self._tab_sensitivity)

        # Global multiplier
        layout.addWidget(QLabel("Global Sensitivity Multiplier:"))
        self._sens_slider = QSlider(Qt.Orientation.Horizontal)
        self._sens_slider.setRange(10, 300)  # 0.1 - 3.0
        self._sens_slider.setValue(100)
        self._sens_label = QLabel("1.00")
        self._sens_slider.valueChanged.connect(lambda v: self._sens_label.setText(f"{v/100:.2f}"))

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

        self._sens_slider.setAccessibleName("Sensitivity Multiplier Slider")
        self._cutoff_slider.setAccessibleName("One Euro Filter Min Cutoff Slider")

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
        self._gestures_tree.setStyleSheet(
            "background-color: #2e2e2e; border: 1px solid #444; color: #fff;"
        )
        layout.addWidget(self._gestures_tree)

        self._record_btn.setAccessibleName("Record Custom Gesture Button")
        self._gestures_tree.setAccessibleName("Predefined and Custom Gestures Table")

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

        self._hud_enabled.setAccessibleName("Enable HUD Checkbox")
        self._hud_opacity.setAccessibleName("HUD Opacity Slider")
        self._show_points.setAccessibleName("Show Joint Tracking Dots Checkbox")
        self._show_ring.setAccessibleName("Show Gesture Progress Ring Checkbox")

        layout.addStretch()

    def _setup_accessibility_tab(self) -> None:
        layout = QVBoxLayout(self._tab_accessibility)

        # 1. Voice Control Group
        from PyQt6.QtWidgets import QGroupBox, QFormLayout, QLineEdit

        voice_group = QGroupBox("Voice Control")
        voice_layout = QVBoxLayout()
        self._voice_enabled = QCheckBox("Enable Voice Control (offline, Vosk)")
        self._voice_enabled.setAccessibleName("Enable voice control checkbox")
        self._voice_enabled.setAccessibleDescription(
            "Check this to enable offline voice command recognition via Vosk."
        )
        voice_layout.addWidget(self._voice_enabled)

        form_layout = QFormLayout()
        self._voice_wake_word = QLineEdit()
        self._voice_wake_word.setAccessibleName("Voice wake word field")
        self._voice_wake_word.setAccessibleDescription(
            "Set the word to say before triggering commands (default: maestro)."
        )
        form_layout.addRow(QLabel("Wake Word:"), self._voice_wake_word)
        voice_layout.addLayout(form_layout)

        self._download_voice_btn = QPushButton("Download Voice Model (~50MB)")
        self._download_voice_btn.clicked.connect(self._download_voice_model)
        self._download_voice_btn.setAccessibleName("Download voice model button")
        self._download_voice_btn.setAccessibleDescription(
            "Click to download and set up the offline Vosk speech model."
        )
        voice_layout.addWidget(self._download_voice_btn)

        voice_group.setLayout(voice_layout)
        layout.addWidget(voice_group)

        # 2. Tremor Compensation Group
        tremor_group = QGroupBox("Tremor Compensation")
        tremor_layout = QVBoxLayout()
        self._tremor_enabled = QCheckBox("Enable Tremor Compensation")
        self._tremor_enabled.setAccessibleName("Enable tremor compensation checkbox")
        self._tremor_enabled.setAccessibleDescription(
            "Dynamically damp high-frequency hand tremors."
        )
        tremor_layout.addWidget(self._tremor_enabled)

        self._calibrate_tremor_btn = QPushButton("Run Tremor Calibration...")
        self._calibrate_tremor_btn.clicked.connect(self._on_calibrate_tremor)
        self._calibrate_tremor_btn.setAccessibleName("Run tremor calibration button")
        self._calibrate_tremor_btn.setAccessibleDescription(
            "Record hand position for 10 seconds to detect peak tremor frequency."
        )
        tremor_layout.addWidget(self._calibrate_tremor_btn)

        tremor_group.setLayout(tremor_layout)
        layout.addWidget(tremor_group)

        # 3. Visual & Styling Group
        visual_group = QGroupBox("Visual & Contrast")
        visual_layout = QVBoxLayout()
        self._high_contrast = QCheckBox("High Contrast Mode")
        self._high_contrast.setAccessibleName("Enable high contrast mode checkbox")
        self._high_contrast.setAccessibleDescription(
            "Increases readability with black backgrounds and bright yellow highlights."
        )
        visual_layout.addWidget(self._high_contrast)

        self._reduced_motion = QCheckBox("Reduced Motion (disable HUD animations)")
        self._reduced_motion.setAccessibleName("Reduced motion checkbox")
        self._reduced_motion.setAccessibleDescription(
            "Disables smooth visual feedback transitions on the screen."
        )
        visual_layout.addWidget(self._reduced_motion)

        visual_group.setLayout(visual_layout)
        layout.addWidget(visual_group)

        # 4. Dwell Clicking Group
        dwell_group = QGroupBox("Dwell Clicking")
        dwell_layout = QVBoxLayout()
        self._dwell_enabled = QCheckBox("Enable Dwell Clicking")
        self._dwell_enabled.setAccessibleName("Enable dwell clicking checkbox")
        self._dwell_enabled.setAccessibleDescription(
            "Automatically trigger mouse click when cursor stays still."
        )
        dwell_layout.addWidget(self._dwell_enabled)

        dwell_form = QFormLayout()
        self._dwell_duration = QSlider(Qt.Orientation.Horizontal)
        self._dwell_duration.setRange(200, 3000)
        self._dwell_duration.setAccessibleName("Dwell duration slider")
        self._dwell_duration.setAccessibleDescription(
            "Sets how long the cursor must stay still before clicking (in milliseconds)."
        )
        self._dwell_label = QLabel("800 ms")
        self._dwell_duration.valueChanged.connect(lambda v: self._dwell_label.setText(f"{v} ms"))
        dwell_form.addRow(self._dwell_duration, self._dwell_label)
        dwell_layout.addLayout(dwell_form)

        dwell_group.setLayout(dwell_layout)
        layout.addWidget(dwell_group)

        layout.addStretch()

    def _on_language_changed(self, index: int) -> None:
        """Live-switch the UI language when the user changes the selector."""
        lang_code = self._lang_combo.itemData(index)
        if not lang_code:
            return
        from gesture_controller.core.i18n import install

        install(lang_code)
        self._config.set("ui.language", lang_code)
        # Inform the user a restart may be needed for all strings to refresh
        import structlog

        structlog.get_logger(__name__).info("Language changed", lang=lang_code)

    def _on_calibrate_tremor(self) -> None:
        from gesture_controller.gui.tremor_calibrator import TremorCalibrator

        calibrator = TremorCalibrator(self._config, self._landmark_callback, parent=self)
        if calibrator.exec():
            self._tremor_enabled.setChecked(self._config.get("filtering.tremor.enabled", False))

    def _download_voice_model(self) -> None:
        self._download_voice_btn.setEnabled(False)
        self._download_voice_btn.setText("Downloading...")

        def run_download():
            import urllib.request
            import zipfile
            from gesture_controller.core.paths import user_data_dir

            model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            model_dir = user_data_dir() / "models"
            model_dir.mkdir(parents=True, exist_ok=True)
            zip_path = model_dir / "vosk-model.zip"

            try:
                urllib.request.urlretrieve(model_url, zip_path)  # nosec B310
                with zipfile.ZipFile(zip_path) as z:
                    z.extractall(model_dir)  # nosec B202
                zip_path.unlink()

                from PyQt6.QtCore import QMetaObject

                QMetaObject.invokeMethod(
                    self, "_on_download_success", Qt.ConnectionType.QueuedConnection
                )
            except Exception as e:
                from PyQt6.QtCore import QMetaObject, Q_ARG

                QMetaObject.invokeMethod(
                    self,
                    "_on_download_failed",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, str(e)),
                )

        import threading

        threading.Thread(target=run_download, daemon=True).start()

    from PyQt6.QtCore import pyqtSlot

    @pyqtSlot()
    def _on_download_success(self) -> None:
        self._download_voice_btn.setText("Download Complete")
        QMessageBox.information(
            self, "Download Successful", "Vosk speech model downloaded and set up successfully!"
        )

    @pyqtSlot(str)
    def _on_download_failed(self, err_msg: str) -> None:
        self._download_voice_btn.setEnabled(True)
        self._download_voice_btn.setText("Download Voice Model (~50MB)")
        QMessageBox.critical(self, "Download Failed", f"Failed to download voice model: {err_msg}")

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
        self._hotkey_widget.setText(
            self._config.get("safety.toggle_recognition_hotkey", "Ctrl+Alt+P")
        )

        # Load accessibility settings
        self._voice_enabled.setChecked(self._config.get("voice.enabled", False))
        self._voice_wake_word.setText(self._config.get("voice.wake_word", "maestro"))
        self._tremor_enabled.setChecked(self._config.get("filtering.tremor.enabled", False))

        theme_val = self._config.get("a11y.theme", "auto")
        self._high_contrast.setChecked(theme_val == "high-contrast")
        self._reduced_motion.setChecked(self._config.get("a11y.reduced_motion", False))
        self._dwell_enabled.setChecked(self._config.get("a11y.dwell_click_enabled", False))
        self._dwell_duration.setValue(self._config.get("a11y.dwell_duration_ms", 800))
        self._dwell_label.setText(f"{self._dwell_duration.value()} ms")

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
                self,
                "Invalid Gesture Name",
                "Gesture name must be 1-64 characters: alphanumeric, dash, or underscore only.",
            )
            return

        if self._template_dir is None:
            QMessageBox.critical(
                self,
                "Cannot Save Gesture",
                "The gesture engine is not connected. Cannot save custom gestures.",
            )
            return

        dest_path = self._template_dir / f"{name}.json"

        # Defense-in-depth: verify the resolved path is still inside template_dir
        try:
            dest_path.resolve().relative_to(self._template_dir.resolve())
        except ValueError:
            QMessageBox.critical(
                self, "Security Error", "Resolved path escapes template directory."
            )
            return

        try:
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2)
            QMessageBox.information(
                self, "Gesture Saved", f"Custom gesture '{name}' saved successfully!"
            )

            # Reload matcher templates
            if self._reload_callback is not None:
                self._reload_callback(self._template_dir)
            elif self._landmark_callback is not None and hasattr(
                self._landmark_callback, "__self__"
            ):
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

        self._config.set("safety.toggle_recognition_hotkey", self._hotkey_widget.text())

        # Save new accessibility settings
        self._config.set("voice.enabled", self._voice_enabled.isChecked())
        self._config.set("voice.wake_word", self._voice_wake_word.text().strip())
        self._config.set("filtering.tremor.enabled", self._tremor_enabled.isChecked())
        self._config.set(
            "a11y.theme", "high-contrast" if self._high_contrast.isChecked() else "auto"
        )
        self._config.set("a11y.reduced_motion", self._reduced_motion.isChecked())
        self._config.set("a11y.dwell_click_enabled", self._dwell_enabled.isChecked())
        self._config.set("a11y.dwell_duration_ms", self._dwell_duration.value())

        # Save to config.yaml file
        user_dir = user_config_dir()
        if user_dir:
            try:
                user_dir.mkdir(parents=True, exist_ok=True)
                config_path = user_dir / "config.yaml"

                # Use ruamel.yaml to preserve comments (S4-6)
                from ruamel.yaml import YAML

                ryaml = YAML()
                ryaml.preserve_quotes = True

                if config_path.exists():
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            user_config = ryaml.load(f) or {}
                    except Exception:
                        user_config = {}
                else:
                    user_config = {}

                # Helper to set nested keys safely
                def set_nested(d, keys, val):
                    for k in keys[:-1]:
                        if k not in d or not isinstance(d[k], dict):
                            d[k] = {}
                        d = d[k]
                    d[keys[-1]] = val

                # Update settings matching settings window inputs
                set_nested(user_config, ["camera", "device_id"], self._camera_device.currentIndex())
                set_nested(
                    user_config,
                    ["sensitivity", "global_multiplier"],
                    self._sens_slider.value() / 100.0,
                )
                set_nested(
                    user_config,
                    ["filter", "one_euro", "min_cutoff"],
                    self._cutoff_slider.value() / 10.0,
                )
                set_nested(user_config, ["hud", "enabled"], self._hud_enabled.isChecked())
                set_nested(user_config, ["hud", "opacity"], self._hud_opacity.value() / 100.0)
                set_nested(
                    user_config, ["hud", "show_tracking_points"], self._show_points.isChecked()
                )
                set_nested(user_config, ["hud", "show_progress_ring"], self._show_ring.isChecked())
                set_nested(
                    user_config, ["safety", "toggle_recognition_hotkey"], self._hotkey_widget.text()
                )

                # Save accessibility settings nested keys
                set_nested(user_config, ["voice", "enabled"], self._voice_enabled.isChecked())
                set_nested(
                    user_config, ["voice", "wake_word"], self._voice_wake_word.text().strip()
                )
                set_nested(
                    user_config,
                    ["filtering", "tremor", "enabled"],
                    self._tremor_enabled.isChecked(),
                )
                set_nested(
                    user_config,
                    ["a11y", "theme"],
                    "high-contrast" if self._high_contrast.isChecked() else "auto",
                )
                set_nested(
                    user_config, ["a11y", "reduced_motion"], self._reduced_motion.isChecked()
                )
                set_nested(
                    user_config, ["a11y", "dwell_click_enabled"], self._dwell_enabled.isChecked()
                )
                set_nested(user_config, ["a11y", "dwell_duration_ms"], self._dwell_duration.value())

                with open(config_path, "w", encoding="utf-8") as f:
                    ryaml.dump(user_config, f)
                logger.info(
                    "Configuration saved successfully to user profile config.yaml, preserving comments"
                )
            except Exception as e:
                logger.error("Failed saving configuration overrides to file", error=str(e))

        # Emit signal to alert engine components
        self.config_changed.emit(self._config._config)
        self.accept()

    # ─────────────────────────────────────────────────────────────────────────
    # Plugins Tab
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_plugins_tab(self) -> None:
        """Build the Plugins management tab."""
        from PyQt6.QtWidgets import (
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QPushButton,
            QHBoxLayout,
            QLabel,
            QFileDialog,
        )
        from PyQt6.QtCore import Qt

        layout = QVBoxLayout(self._tab_plugins)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # ── Header ───────────────────────────────────────────────────────────
        header = QLabel("Installed Plugins")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # ── Search registry bar ───────────────────────────────────────────────
        search_row = QHBoxLayout()
        self._plugin_search = QLineEdit()
        self._plugin_search.setPlaceholderText("Search plugin registry…")
        self._plugin_search.setAccessibleName("Plugin registry search")
        search_row.addWidget(self._plugin_search)
        self._plugin_search_btn = QPushButton("Search")
        self._plugin_search_btn.setAccessibleName("Search plugin registry")
        self._plugin_search_btn.clicked.connect(self._on_plugin_registry_search)
        search_row.addWidget(self._plugin_search_btn)
        layout.addLayout(search_row)

        # ── Plugin list ───────────────────────────────────────────────────────
        self._plugin_list = QListWidget()
        self._plugin_list.setAccessibleName("Installed plugins list")
        self._plugin_list.setMinimumHeight(180)
        layout.addWidget(self._plugin_list)

        self._populate_plugin_list()

        # ── Registry results ──────────────────────────────────────────────────
        self._registry_label = QLabel("Registry results:")
        self._registry_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        self._registry_label.setVisible(False)
        layout.addWidget(self._registry_label)

        self._registry_list = QListWidget()
        self._registry_list.setAccessibleName("Plugin registry search results")
        self._registry_list.setMinimumHeight(80)
        self._registry_list.setVisible(False)
        layout.addWidget(self._registry_list)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._plugin_enable_btn = QPushButton("Enable")
        self._plugin_enable_btn.setAccessibleName("Enable selected plugin")
        self._plugin_enable_btn.clicked.connect(self._on_plugin_enable)
        btn_row.addWidget(self._plugin_enable_btn)

        self._plugin_disable_btn = QPushButton("Disable")
        self._plugin_disable_btn.setAccessibleName("Disable selected plugin")
        self._plugin_disable_btn.clicked.connect(self._on_plugin_disable)
        btn_row.addWidget(self._plugin_disable_btn)

        self._plugin_uninstall_btn = QPushButton("Uninstall")
        self._plugin_uninstall_btn.setAccessibleName("Uninstall selected plugin")
        self._plugin_uninstall_btn.setStyleSheet("color: #ff6b6b;")
        self._plugin_uninstall_btn.clicked.connect(self._on_plugin_uninstall)
        btn_row.addWidget(self._plugin_uninstall_btn)

        btn_row.addStretch()

        self._plugin_install_file_btn = QPushButton("Install from File…")
        self._plugin_install_file_btn.setAccessibleName("Install plugin from local file")
        self._plugin_install_file_btn.clicked.connect(self._on_plugin_install_file)
        btn_row.addWidget(self._plugin_install_file_btn)

        layout.addLayout(btn_row)
        layout.addStretch()

    def _get_plugin_manager(self):
        """Lazily initialise and return a PluginManager instance."""
        if not hasattr(self, "_plugin_manager") or self._plugin_manager is None:
            try:
                from gesture_controller.plugins.plugin_manager import PluginManager
                from gesture_controller.core.event_bus import EventBus

                self._plugin_manager = PluginManager(EventBus(), self._config)
                self._plugin_manager.load_all()
            except Exception as e:
                logger.warning("Could not initialise PluginManager", error=str(e))
                self._plugin_manager = None
        return self._plugin_manager

    def _populate_plugin_list(self) -> None:
        """Refresh the plugin list widget from the PluginManager."""
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtCore import Qt

        self._plugin_list.clear()
        manager = self._get_plugin_manager()
        if manager is None:
            self._plugin_list.addItem("(No plugins found)")
            return
        for record in manager.list_plugins():
            status = "✓" if record.enabled else "✗"
            label = f"{status}  {record.name}  v{record.version} — {record.description[:60]}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, record.name)
            self._plugin_list.addItem(item)

    def _selected_plugin_name(self) -> str | None:
        from PyQt6.QtCore import Qt

        item = self._plugin_list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_plugin_enable(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        name = self._selected_plugin_name()
        if not name:
            return
        manager = self._get_plugin_manager()
        if manager and manager.enable(name):
            self._populate_plugin_list()

    def _on_plugin_disable(self) -> None:
        name = self._selected_plugin_name()
        if not name:
            return
        manager = self._get_plugin_manager()
        if manager and manager.disable(name):
            self._populate_plugin_list()

    def _on_plugin_uninstall(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        name = self._selected_plugin_name()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Uninstall Plugin",
            f"Uninstall '{name}'? This will remove its files from disk.",
        )
        from PyQt6.QtWidgets import QMessageBox as QMB

        if reply == QMB.StandardButton.Yes:
            manager = self._get_plugin_manager()
            if manager and manager.uninstall(name):
                self._populate_plugin_list()

    def _on_plugin_install_file(self) -> None:
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path

        path_str, _ = QFileDialog.getOpenFileName(
            self, "Select Plugin File", "", "Python Plugins (*.py);;All Files (*)"
        )
        if not path_str:
            return
        manager = self._get_plugin_manager()
        if manager:
            record = manager.install_from_path(Path(path_str))
            if record:
                QMessageBox.information(
                    self,
                    "Plugin Installed",
                    f"'{record.name}' v{record.version} installed successfully.",
                )
                self._populate_plugin_list()
            else:
                QMessageBox.warning(
                    self,
                    "Install Failed",
                    "Could not install the plugin. Check the log for details.",
                )

    def _on_plugin_registry_search(self) -> None:
        from PyQt6.QtWidgets import QListWidgetItem

        query = self._plugin_search.text().strip()
        if not query:
            self._registry_list.setVisible(False)
            self._registry_label.setVisible(False)
            return
        manager = self._get_plugin_manager()
        results = manager.search_registry(query) if manager else []
        self._registry_list.clear()
        for entry in results:
            label = f"{entry.get('name')}  v{entry.get('version')} — {entry.get('description', '')}"
            self._registry_list.addItem(QListWidgetItem(label))
        if not results:
            self._registry_list.addItem("No results found.")
        self._registry_label.setVisible(True)
        self._registry_list.setVisible(True)
