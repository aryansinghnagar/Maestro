# Maestro Accessibility & Universal Design

Maestro is built from the ground up to adhere to **WCAG 2.2 AA** universal accessibility standards, enabling users with essential tremor, Parkinson's disease, repetitive strain injuries (RSI), or limited motor control to interact with desktop computers hands-free.

---

## 1. Jitter Suppression & Adaptive One-Euro Filtering

Standard webcam landmark detectors frequently exhibit high-frequency coordinate jitter. To deliver smooth, stable mouse cursor control without introducing sluggish lag, Maestro applies a dual-adaptive **One-Euro low-pass filter** (`one_euro_filter.py`):

\[
\alpha = \frac{1}{1 + \frac{\tau}{T_e}}, \quad \tau = \frac{1}{2\pi (f_c + \beta |\dot{x}|)}
\]

- **Low Velocity ($|\dot{x}| \to 0$)**: The cutoff frequency drops to `min_cutoff` (default: `1.0 Hz`), filtering out subtle hand tremors and sensor noise.
- **High Velocity ($|\dot{x}| \gg 0$)**: The cutoff frequency scales with speed coefficient `beta` (default: `0.007`), reducing phase lag so fast cursor movements remain instantaneous.

---

## 2. Live Tremor Calibration Wizard

Because tremor frequencies and amplitudes vary widely between individuals, Maestro includes an automated **Tremor Calibration Wizard** (`tremor_calibrator.py`):

```
  [Start Calibration] ──> [Sample 500ms Window] ──> [FFT Variance Analysis] ──> [Save OneEuro Parameters]
```

1. Launch **Tremor Calibration** from the system tray menu.
2. Hold your hand stationary in front of the camera for 5 seconds.
3. The wizard calculates the standard deviation $\sigma_x, \sigma_y$ and dominant oscillation frequency.
4. Optimal values for `min_cutoff`, `beta`, and `max_displacement_px` are calculated and saved directly into `config.yaml`.

---

## 3. Hands-Free Dwell-to-Click Engine

For users unable to perform rapid pinch or fist gestures, Maestro provides a **Dwell Clicker** (`dwell_clicker.py`):

1. Position the cursor over a UI button or link.
2. Maintain your hand within a small tolerance bounding radius (default: `20 pixels`) for the dwell duration (default: `800ms`).
3. An animated translucent circular progress ring fills around the pointer.
4. When the countdown completes, Maestro generates a native OS `LeftClick` (or configured double-click/right-click).

---

## 4. Screen Reader & Assistive Technology Integration

All PyQt6 dialogs, wizards, and tray menus implement full Qt Accessibility APIs:

- **Accessible Names & Descriptions**: Every widget sets `setAccessibleName()` and `setAccessibleDescription()` providing contextual announcements to screen readers.
- **Screen Reader Compatibility**: Verified against:
  - **Windows**: NVDA (NonVisual Desktop Access) and JAWS via UI Automation (UIA)
  - **macOS**: VoiceOver via NSAccessibility protocols
  - **Linux**: Orca via AT-SPI2 D-Bus bridges

---

## 5. Keyboard Navigation & High Contrast Themes

- **100% Keyboard Accessible**: Every dialog and configuration tab in Maestro can be fully traversed using `Tab`, `Shift+Tab`, `Space`, `Enter`, and standard arrow keys.
- **High-Contrast Theme**: Features a WCAG 2.2 AA compliant palette with contrast ratios exceeding `7:1` for text and `4.5:1` for UI components.
- **Colorblind-Safe HUD**: Visual indicators avoid relying solely on color coding, pairing color states with distinct geometric shapes (circles, squares, rings).

