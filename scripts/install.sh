#!/bin/bash
# ============================================================
#  ADS-B Dashboard  —  Installation Script
#  Run as root on a fresh Raspberry Pi OS Lite image.
#  Tested on RPi 3 Model B, Raspberry Pi OS Lite (Bookworm).
# ============================================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

[ "$(id -u)" -eq 0 ] || error "Run as root: sudo bash install.sh"

INSTALL_DIR="/opt/adsb-dashboard"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PI_USER="${SUDO_USER:-pi}"

info "=== ADS-B Dashboard Installer ==="
info "Install dir : $INSTALL_DIR"
info "Pi user     : $PI_USER"
echo ""

# ── 1. System update ─────────────────────────────────────────────────────
info "Updating system packages…"
apt-get update -qq
apt-get upgrade -y -qq

# ── 2. Core packages ─────────────────────────────────────────────────────
info "Installing core packages…"
apt-get install -y -qq \
  python3 python3-pip python3-venv \
  git curl wget \
  rtl-sdr \
  librtlsdr-dev \
  chromium-browser \
  xorg xinit x11-xserver-utils \
  openbox \
  network-manager \
  hostapd dnsmasq \
  lighttpd \
  unzip \
  fonts-liberation \
  libgl1 \
  libmtdev1t64 \
  libgles2 \
  libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  xdotool

# ── 3. dump1090-fa ───────────────────────────────────────────────────────
info "Installing dump1090-fa…"
if ! command -v dump1090-fa &>/dev/null; then
  # FlightAware repository
  wget -q -O /tmp/flightaware.gpg \
    https://flightaware.com/adsb/piaware/files/packages/pool/piaware/f/flightaware-apt-repository/flightaware-apt-repository_1.1_all.deb
  dpkg -i /tmp/flightaware.gpg 2>/dev/null || true
  apt-get update -qq
  apt-get install -y -qq dump1090-fa || {
    warn "FlightAware repo failed, trying alternative build…"
    apt-get install -y -qq dump1090-mutability || true
  }
else
  info "dump1090-fa already installed."
fi

# ── 4. Python dependencies ───────────────────────────────────────────────
info "Installing Python packages…"
pip3 install --break-system-packages \
  kivy[base]==2.3.0 \
  flask \
  requests

# ── 5. Deploy application files ──────────────────────────────────────────
info "Deploying application…"
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/dashboard" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/backend"   "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/web"       "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/config"    "$INSTALL_DIR/"

chown -R "$PI_USER:$PI_USER" "$INSTALL_DIR"

# ── 6. Systemd services ───────────────────────────────────────────────────
info "Installing systemd services…"
cp "$SCRIPT_DIR/services/dump1090-fa.service"  /etc/systemd/system/
cp "$SCRIPT_DIR/services/adsb-backend.service" /etc/systemd/system/
cp "$SCRIPT_DIR/services/adsb-dashboard.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable dump1090-fa
systemctl enable adsb-backend
systemctl enable adsb-dashboard

# ── 7. Autologin + auto-start X ─────────────────────────────────────────
info "Configuring autologin…"
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $PI_USER --noclear %I \$TERM
EOF

# .bash_profile launches X on login if not already running
BASH_PROFILE="/home/$PI_USER/.bash_profile"
if ! grep -q 'startx' "$BASH_PROFILE" 2>/dev/null; then
  cat >> "$BASH_PROFILE" <<'EOF'

# Auto-start X on tty1
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  exec startx
fi
EOF
fi

# Openbox autostart — launches dashboard instead of a desktop
mkdir -p "/home/$PI_USER/.config/openbox"
cat > "/home/$PI_USER/.config/openbox/autostart" <<'EOF'
# Disable screen blanking
xset s off &
xset -dpms &
xset s noblank &

# Hide cursor after 1 second of inactivity
unclutter -idle 1 -root &

# Start the ADS-B dashboard
python3 /opt/adsb-dashboard/dashboard/main.py &
EOF
chown -R "$PI_USER:$PI_USER" "/home/$PI_USER/.config"

# .xinitrc — start openbox
cat > "/home/$PI_USER/.xinitrc" <<'EOF'
exec openbox-session
EOF
chown "$PI_USER:$PI_USER" "/home/$PI_USER/.xinitrc"

# ── 8. RTL-SDR udev rules ────────────────────────────────────────────────
info "Adding RTL-SDR udev rules…"
cat > /etc/udev/rules.d/20-rtlsdr.rules <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0666", SYMLINK+="rtl_sdr"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666", SYMLINK+="rtl_sdr"
EOF
usermod -aG plugdev "$PI_USER"

# ── 9. Blacklist DVB kernel module (conflicts with RTL-SDR) ─────────────
info "Blacklisting DVB kernel modules…"
cat > /etc/modprobe.d/rtlsdr-blacklist.conf <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF

# ── 10. GPU memory split for Pi 3 ───────────────────────────────────────
info "Setting GPU memory split…"
if ! grep -q 'gpu_mem' /boot/config.txt 2>/dev/null; then
  echo 'gpu_mem=128' >> /boot/config.txt
fi
# Force HDMI even without display attached
if ! grep -q 'hdmi_force_hotplug' /boot/config.txt 2>/dev/null; then
  echo 'hdmi_force_hotplug=1' >> /boot/config.txt
fi

# ── 11. Touchscreen permissions ──────────────────────────────────────────
usermod -aG input "$PI_USER"
usermod -aG video "$PI_USER"

# ── 12. Default hotspot config ───────────────────────────────────────────
mkdir -p "$INSTALL_DIR/config"
if [ ! -f "$INSTALL_DIR/config/hotspot.json" ]; then
  cat > "$INSTALL_DIR/config/hotspot.json" <<'EOF'
{
  "ssid": "ADSB-RADAR",
  "password": "aircraft123",
  "channel": 6,
  "interface": "wlan0",
  "ip": "192.168.4.1"
}
EOF
fi
chown "$PI_USER:$PI_USER" "$INSTALL_DIR/config/hotspot.json"

# ── Done ─────────────────────────────────────────────────────────────────
echo ""
info "=========================================="
info " Installation complete!"
info "=========================================="
info " Reboot to start the dashboard:"
info "   sudo reboot"
info ""
info " Web interface (when hotspot active):"
info "   http://192.168.4.1"
info ""
info " Connect RTL-SDR dongle before rebooting."
info "=========================================="
