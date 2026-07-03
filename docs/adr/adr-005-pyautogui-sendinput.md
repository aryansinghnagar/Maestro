# ADR-005: PyAutoGUI vs SendInput API Wrapper for Windows Controller

## Status
Accepted

## Context
For simulating keyboard and mouse inputs on Windows, we need a reliable, high-performance mechanism. The two primary options are:
1. **PyAutoGUI**: A high-level, cross-platform python library that simulates input events.
2. **Win32 SendInput API (via ctypes/pywin32)**: Direct calling of Windows API `SendInput` functions.

## Decision
We choose PyAutoGUI as the primary simulation method on Windows, but configure `pyautogui.FAILSAFE = False` to prevent user session termination when mouse coordinates hit screen corners. In the future, a fallback or direct path to Win32 `SendInput` may be implemented if gaming or security-hardened applications require bypassing high-level hooks.

## Consequences
- **Pros**:
  - Extremely easy to use and maintain.
  - Handles screen-resolution scaling and coordinate mapping automatically.
  - Safe, standardized key naming mapping matching general keys.
- **Cons**:
  - Slightly higher overhead than direct Win32 API calls.
  - Easily detectable by anti-cheat systems if used in games.
