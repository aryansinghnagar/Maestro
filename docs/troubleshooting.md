# Maestro Troubleshooting & Diagnostics

This guide provides practical solutions to common issues with camera acquisition, OS input permissions, voice recognition, performance throttling, and crash diagnostics.

---

## 1. Camera & Video Stream Issues

### "Camera device not found" or `IndexError`
- **Cause**: The default camera index (`0`) is occupied or not detected.
- **Solution**:
  1. Open **Settings → Vision → Camera Device** and select alternative devices (Index 1, 2, etc.).
  2. Verify your camera is recognized by the OS (Device Manager on Windows, System Information on macOS, `v4l2-ctl --list-devices` on Linux).
  3. Close other applications that may have an exclusive lock on the camera (Zoom, Microsoft Teams, OBS Studio).

### Camera Permission Denied
- **Windows**: Navigate to **Settings → Privacy & Security → Camera**. Ensure **Camera access** and **Let desktop apps access your camera** are toggled **ON**.
- **macOS**: Go to **System Settings → Privacy & Security → Camera** and ensure your terminal emulator / Python executable is checked. If permissions are corrupted, reset them via terminal:
  ```bash
  tccutil reset Camera
  ```
- **Linux**: Verify your user belongs to the `video` group:
  ```bash
  sudo usermod -aG video $USER
  ```
  Then log out and log back in.

---

## 2. OS Input Injection Issues

### Input Not Injected into Elevated (Admin) Windows on Windows
- **Cause**: Windows User Interface Privilege Isolation (UIPI) blocks input sent from a non-elevated process to an Administrator window (e.g. Task Manager, elevated PowerShell).
- **Solution**: Run Maestro's privilege-separated broker service or launch Maestro as Administrator. Validate peer SID authentication via:
  ```bash
  maestro verify-audit-log
  ```

### Gestures Detected but No Mouse/Keyboard Actions on macOS
- **Cause**: Missing macOS Accessibility or Input Monitoring permissions.
- **Solution**:
  1. Open **System Settings → Privacy & Security → Accessibility**.
  2. Add and enable your terminal emulator or `Maestro`.
  3. Open **System Settings → Privacy & Security → Input Monitoring** and ensure the app is enabled.

### Permission Denied on `/dev/uinput` (Linux)
- **Cause**: Linux requires specific udev permissions to write to `/dev/uinput`.
- **Solution**:
  ```bash
  sudo usermod -aG input $USER
  sudo cp packaging/99-gesture-controller-uinput.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
  Log out and back in to apply group changes.

---

## 3. Offline Voice Control Issues

### "Vosk voice model not found"
- **Cause**: The ~50MB offline speech model has not been downloaded.
- **Solution**:
  Download the verified model using the CLI:
  ```bash
  maestro download-voice-model
  ```

### PyAudio Stream Initialization Error
- **Cause**: Missing system audio development libraries.
- **Solution**:
  - **Linux (Ubuntu/Debian)**: `sudo apt-get install portaudio19-dev libasound2-dev`
  - **macOS**: `brew install portaudio`
  - **Windows**: Ensure `pyaudio` wheel was installed via `pip install "gesture-controller[voice]"`

---

## 4. Performance & High Latency

### Frame Rate Drops or High Latency (>30ms)
- **Check Hardware Tier**: Look at the active tier in the Performance Monitor. If the tier has dropped to `T2` or `T3`, Maestro is conserving CPU/battery.
- **Enable GPU Acceleration**:
  - **Windows**: Ensure DirectML package is installed (`onnxruntime-directml`).
  - **Linux (NVIDIA)**: Install CUDA 12 and cuDNN or TensorRT libraries.
  - **macOS**: Apple Silicon M1/M2/M3 chips automatically leverage CoreML acceleration.
- **Lighting Conditions**: Low lighting increases camera sensor exposure time, capping FPS at 15–20. Ensure adequate, even illumination on your hands.

---

## 5. Configuration Reset & Diagnostics

### Resetting Configuration to Factory Defaults
To completely wipe corrupted configuration and reset to fresh defaults:
```bash
maestro erase
```

### Exporting Diagnostic Bundles for Bug Reports
To generate a sanitized diagnostic archive containing anonymized crash dumps, hardware probes, and tier logs:
```bash
maestro export --output maestro-diagnostics.zip
```
Attach `maestro-diagnostics.zip` when reporting issues at [github.com/aryansinghnagar/Maestro/issues](https://github.com/aryansinghnagar/Maestro/issues).

