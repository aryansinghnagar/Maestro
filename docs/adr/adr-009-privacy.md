# ADR-009: Privacy-by-Design Landmark Extraction Logic

## Status
Accepted

## Context
Desktop gesture control requires processing webcam video streams, presenting potential privacy risks if raw video data or recognizable faces are leaked, stored, or transmitted.

## Decision
We enforce a strict privacy-by-design architecture:
1. **Local-Only Processing**: No image frames, landmarks, or custom gesture records are transmitted over the network. MediaPipe Hand Landmarker runs entirely locally on the device CPU/GPU.
2. **Immediate Frame Discard**: Raw video frames read from the camera sub-process are written to a single-slot `SharedMemory` buffer and immediately overwritten by the next frame. Raw frames are never written to disk.
3. **Landmark-Only HUD**: The transparent overlay display renders only skeletal joint coordinates (lines and dots) and never displays the actual camera video stream to the user, preventing ambient screen recording leaks.

## Consequences
- **Pros**:
  - Negligible risk of private user or background room video leakage.
  - Minimal local storage requirements (only YAML settings and small JSON custom template files are saved).
- **Cons**:
  - Troubleshooting tracking issues is slightly harder for users since they cannot view their camera feed inside the application.
