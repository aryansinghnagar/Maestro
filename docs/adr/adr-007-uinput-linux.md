# ADR-007: Linux Wayland /dev/uinput Virtual Device Configuration

## Status
Accepted

## Context
Wayland security restrictions prevent traditional tools like `xdotool` or `xte` from injecting keyboard and mouse events globally. To make the gesture controller fully cross-platform and compatible with Wayland compositor architectures (GNOME, KDE, wlroots), we need a kernel-level input simulation layer.

## Decision
We choose to use `/dev/uinput` via the Python `evdev` library to simulate keyboard and mouse devices at the OS level on Linux. We fall back to `xdotool`, `playerctl`, and `pactl` subprocess commands if uinput permissions are missing or when control operations (such as audio volume or media play/pause) are better handled via command line utilities.

## Consequences
- **Pros**:
  - Works natively under Wayland and X11 environments.
  - Undetectable as virtual software hooks, behaving like a physical USB keyboard/mouse.
  - High performance, bypassing XServer or compositor event queues.
- **Cons**:
  - Requires write permissions to `/dev/uinput`, necessitating a udev rule setup during installation:
    `KERNEL=="uinput", GROUP="input", MODE="0660"`
  - Package dependencies require compiling `evdev` C-extensions on Linux.
