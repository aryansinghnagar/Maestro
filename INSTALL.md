# Installation Guide

This document describes how to install Maestro on Windows, macOS, and Linux.

## Platform Specific Instructions

### Windows
1. Download the latest installer `.exe` from [Releases](https://github.com/aryansinghnagar/Maestro/releases).
2. Run the installer and follow the onboarding wizard steps.
3. Make sure to install the Visual C++ Redistributable when prompted.

### macOS
1. Install using Homebrew:
```bash
brew install python@3.11
pip install gesture-controller
```
2. Grant camera and accessibility permissions on first launch.

### Linux
1. Run the installer script:
```bash
bash packaging/linux/install.sh
```
2. Grant access to the `uinput` interface:
```bash
sudo usermod -aG input $USER
```
3. Log out and back in to apply group changes.
