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
REPO_DIR="$(dirname "$SCRIPT_DIR")"
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

# ── 3. dump1090-fa (build from source) ───────────────────────────────────
info "Installing dump1090-fa from source…"
if ! command -v dump1090-fa &>/dev/null; then
  apt-get install -y -qq \
    build-essential \
    debhelper \
    libusb-1.0-0-dev \
    pkg-config \
    libncurses-dev

  DUMP1090_SRC="/tmp/dump1090"
  rm -rf "$DUMP1090_SRC"
  git clone --depth 1 https://github.com/flightaware/dump1090.git "$DUMP1090_SRC"
  cd "$DUMP1090_SRC"
  make BLADERF=no HACKRF=no LIMESDR=no
  cp dump1090 /usr/local/bin/dump1090-fa
  cp view1090 /usr/local/bin/view1090 2>/dev/null || true
  mkdir -p /usr/share/dump1090-fa/html
  cp -r public_html/* /usr/share/dump1090-fa/html/ 2>/dev/null || true
  cd /
  rm -rf "$DUMP1090_SRC"
  info "dump1090-fa built and installed."
else
  info "dump1090-fa already installed."
fi

# ── 4. Python dependencies ───────────────────────────────────────────────
info "Creating swap file to prevent OOM during Kivy build…"
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
fi
swapon /swapfile 2>/dev/null || true

info "Installing Python packages (Kivy will compile — takes ~15 mins)…"
pip3 install --break-system-packages \
  "kivy[base]" \
  flask \
  requests

# ── 5. Deploy application files ──────────────────────────────────────────
info "Deploying application…"
mkdir -p "$INSTALL_DIR"
cp -r "$REPO_DIR/dashboard" "$INSTALL_DIR/"
cp -r "$REPO_DIR/backend"   "$INSTALL_DIR/"
cp -r "$REPO_DIR/web"       "$INSTALL_DIR/"
cp -r "$REPO_DIR/config"    "$INSTALL_DIR/"

chown -R "$PI_USER:$PI_USER" "$INSTALL_DIR"

# ── 6. Systemd services ───────────────────────────────────────────────────
info "Installing systemd services…"
cp "$REPO_DIR/services/dump1090-fa.service"    /etc/systemd/system/
cp "$REPO_DIR/services/adsb-backend.service"   /etc/systemd/system/
cp "$REPO_DIR/services/adsb-dashboard.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable dump1090-fa
systemctl enable adsb-backend
systemctl enable adsb-dashboard

# ── 7. Autologin + auto-start X ──────────────────────────────────────────
info "Configuring autologin…"
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $PI_USER --noclear %I \$TERM
EOF

BASH_PROFILE="/home/$PI_USER/.bash_profile"
if ! grep -q 'startx' "$BASH_PROFILE" 2>/dev/null; then
  cat >> "$BASH_PROFILE" <<'EOF'

# Auto-start X on tty1
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  exec startx
fi
EOF
fi

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

# ── 9. Blacklist DVB kernel module (conflicts with RTL-SDR) ──────────────
info "Blacklisting DVB kernel modules…"
cat > /etc/modprobe.d/rtlsdr-blacklist.conf <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF

# ── 10. GPU memory split for Pi 3 ────────────────────────────────────────
info "Setting GPU memory split…"
if ! grep -q 'gpu_mem' /boot/config.txt 2>/dev/null; then
  echo 'gpu_mem=128' >> /boot/config.txt
fi
if ! grep -q 'hdmi_force_hotplug' /boot/config.txt 2>/dev/null; then
  echo 'hdmi_force_hotplug=1' >> /boot/config.txt
fi

# ── 11. Touchscreen permissions ───────────────────────────────────────────
usermod -aG input "$PI_USER"
usermod -aG video "$PI_USER"

# ── 12. Default hotspot config ────────────────────────────────────────────
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

# ── Done ──────────────────────────────────────────────────────────────────
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
