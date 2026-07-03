#!/bin/bash
set -e

# Maestro Linux Installer Script
# Configures udev rules and systemd services

echo "=== Maestro Installation & Configuration ==="

# 1. Create dedicated gesture-controller group if not exists
if ! getent group gesture-controller > /dev/null; then
    echo "Creating system group 'gesture-controller'..."
    sudo groupadd -r gesture-controller
fi

# 2. Add current user to group
CURRENT_USER=$(logname || echo $USER)
echo "Adding user '$CURRENT_USER' to group 'gesture-controller'..."
sudo usermod -aG gesture-controller "$CURRENT_USER"

# 3. Install udev rule for non-root uinput access
echo "Deploying udev rules..."
sudo cp udev/99-gesture-controller-uinput.rules /etc/udev/rules.d/ 2>/dev/null || sudo cp 99-gesture-controller-uinput.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# 4. Install systemd user service
echo "Deploying systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
cp linux/gesture-controller.service "$HOME/.config/systemd/user/" 2>/dev/null || cp gesture-controller.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable gesture-controller.service

echo "=== Installation complete! ==="
echo "NOTE: Please log out and log back in for group membership changes to take effect."
