#!/bin/bash
set -e

# Maestro Linux Installer Script
# Configures udev rules and systemd services

echo "=== Maestro Installation & Configuration ==="

# ReAct fix: standard video/input groups own /dev/video* and /dev/uinput on
# most distros. We add the user to those AND keep the dedicated group for
# the shipped udev rule. Matches INSTALL.md (was contradictory).
# 1. Ensure groups exist / add user
CURRENT_USER=$(logname 2>/dev/null || echo "${SUDO_USER:-$USER}")
for grp in input video gesture-controller; do
    if ! getent group "$grp" > /dev/null; then
        echo "Creating system group '$grp'..."
        sudo groupadd -r "$grp" || true
    fi
    echo "Adding user '$CURRENT_USER' to group '$grp'..."
    sudo usermod -aG "$grp" "$CURRENT_USER" || true
done

# 2. Wayland notice (xdotool path is X11-only; uinput works on both)
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo "NOTE: Wayland detected — X11 helpers (xdotool) are disabled; uinput path will be used."
fi

# 3. Install udev rule for non-root uinput access (resolve script dir first)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Deploying udev rules..."
if [ -f "$SCRIPT_DIR/../99-gesture-controller-uinput.rules" ]; then
    sudo cp "$SCRIPT_DIR/../99-gesture-controller-uinput.rules" /etc/udev/rules.d/
elif [ -f "$SCRIPT_DIR/99-gesture-controller-uinput.rules" ]; then
    sudo cp "$SCRIPT_DIR/99-gesture-controller-uinput.rules" /etc/udev/rules.d/
else
    sudo cp udev/99-gesture-controller-uinput.rules /etc/udev/rules.d/ 2>/dev/null || sudo cp 99-gesture-controller-uinput.rules /etc/udev/rules.d/
fi
sudo udevadm control --reload-rules
sudo udevadm trigger || true

# 4. Install systemd user service
echo "Deploying systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
cp linux/gesture-controller.service "$HOME/.config/systemd/user/" 2>/dev/null || cp gesture-controller.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable gesture-controller.service

echo "=== Installation complete! ==="
echo "NOTE: Please log out and log back in for group membership changes to take effect."
