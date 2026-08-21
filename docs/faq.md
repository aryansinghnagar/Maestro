# Frequently Asked Questions (FAQ)

Find answers to common questions about Maestro's privacy architecture, hardware requirements, gaming compatibility, and multi-monitor support.

---

### 1. Privacy & Offline Operation

#### Is my webcam video or audio ever transmitted over the internet?
**No, never.** Maestro operates on a strict **Zero Network Egress** security policy. All computer vision inference (MediaPipe / ONNX Runtime) and speech recognition (Vosk) execute 100% locally on your device's CPU/GPU. No video frames, landmark coordinates, voice audio, or keystrokes leave your machine.

#### Does Maestro require an active internet connection?
No. Once installed, Maestro functions completely offline. The only network requests occur when you explicitly initiate an auto-update check or run the plugin marketplace search.

---

### 2. Performance & Hardware

#### Will Maestro drain my laptop's battery?
Maestro features an **Adaptive Performance Tier Manager (T0–T3)** that automatically reduces frame rate, inference resolution, and model precision when running on battery power or when system CPU load exceeds thresholds. On modern laptops, Maestro typically consumes less than 4% CPU in balanced mode.

#### Does Maestro require a dedicated NVIDIA GPU?
No. While NVIDIA GPUs benefit from TensorRT and CUDA acceleration, Maestro runs efficiently across diverse platforms:
- **Windows**: Uses DirectML for hardware acceleration across Intel, AMD, and NVIDIA GPUs.
- **macOS**: Uses CoreML on Apple Silicon (M1/M2/M3/M4) Neural Engine and GPU.
- **CPU Fallback**: Uses optimized AVX2 SIMD routines for fast CPU execution.

---

### 3. Gesture Recognition & Controls

#### Can I use both hands simultaneously?
Yes. Maestro tracks up to two hands concurrently (configurable via `engine.max_hands` in `config.yaml`). Two-hand gestures such as zoom spread/pinch and two-handed window management are supported out of the box.

#### How accurate are custom recorded DTW gestures?
Maestro normalizes 21-point hand landmark sequences for translation, rotation, and hand scale before computing Dynamic Time Warping (DTW) distance matrices. Recording a distinct, intentional motion 3 times in the wizard typically yields `>98%` recognition accuracy.

#### Can I use Maestro across multiple monitors?
Yes. Maestro fully supports multi-monitor setups, virtual desktops, and mixed-DPI scaling across Windows, macOS, and Linux. The HUD overlay automatically positions itself on your primary display or follows cursor focus.

---

### 4. Compatibility & Security

#### Will Maestro interfere with games or anti-cheat software?
Maestro simulates standard OS input events via native operating system APIs (`SendInput` on Windows, `CGEvent` on macOS, `uinput` on Linux). For administrative windows or protected anti-cheat games, the privilege-separated input broker ensures secure, authenticated event routing.

#### How do I temporarily pause gesture recognition when typing?
- **Global Hotkey**: Press `Ctrl+Alt+P` to instantly toggle pause/resume.
- **Voice Command**: Say `"maestro pause recognition"`.
- **System Tray**: Right-click the tray icon and select **Pause Recognition**.
- **Auto-Suppress**: Maestro automatically suspends gesture triggers during rapid physical keyboard typing.

