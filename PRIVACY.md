# Privacy Policy

Maestro processes all data on your device. We do not collect, transmit, or store:
- Camera frames
- Hand landmark data
- Foreground application names
- Gesture usage data

## Camera
Maestro accesses your webcam to detect hand landmarks. Frames are processed in RAM and never written to disk. Frames are not accessible to plugins.

## Logging
Maestro logs diagnostic information (error messages, performance metrics) to local log files. Logs do not contain hand data or application names (unless debug mode is explicitly enabled).

## Telemetry
Maestro does not collect telemetry. The `telemetry_enabled` config flag is dead code in v2.0.

## Updates
Maestro checks for updates securely using The Update Framework (TUF). Update checks are performed over HTTPS with signature and metadata verification. No user-identifying data is sent.

## Data Export & Deletion
Run `maestro export` to export all your data (config, templates, redacted logs).
Run `maestro erase` to delete all Maestro data from your system.
