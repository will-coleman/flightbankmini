# ADS-B RADAR — Complete Instruction Manual

**Version 1.0 — Raspberry Pi 3 ADS-B Receiver Appliance**

---

## Table of Contents

1. [What This System Does](#1-what-this-system-does)
2. [Hardware Requirements](#2-hardware-requirements)
3. [Software Architecture](#3-software-architecture)
4. [File Structure Reference](#4-file-structure-reference)
5. [Installation Guide](#5-installation-guide)
6. [First Boot & Configuration](#6-first-boot--configuration)
7. [Using the Touchscreen Dashboard](#7-using-the-touchscreen-dashboard)
8. [Using the Web Interface](#8-using-the-web-interface)
9. [WiFi Hotspot Setup](#9-wifi-hotspot-setup)
10. [System Services Reference](#10-system-services-reference)
11. [Configuration Files](#11-configuration-files)
12. [Troubleshooting](#12-troubleshooting)
13. [Security Notes](#13-security-notes)
14. [Future Upgrades](#14-future-upgrades)
15. [Technology Decisions Explained](#15-technology-decisions-explained)

---

## 1. What This System Does

The ADS-B RADAR appliance turns a Raspberry Pi 3 + RTL-SDR USB dongle into a
dedicated aircraft receiver. It:

- Decodes ADS-B transmissions from aircraft within approximately 200–350 km
- Shows a live aircraft map on an attached touchscreen
- Broadcasts a WiFi hotspot so phones and laptops can view the same map
- Displays live system health (CPU, temperature, RAM, uptime)
- Requires no keyboard, mouse, or desktop environment to operate
- Boots directly into the dashboard in approximately 25–35 seconds

The visual design matches professional aviation equipment — industrial, card-based,
no decorative elements, large touch targets.

---

## 2. Hardware Requirements

### Required
| Item | Notes |
|------|-------|
| Raspberry Pi 3 Model B or B+ | B+ preferred (better WiFi antenna) |
| MicroSD card — 16 GB minimum, 32 GB recommended | Class 10 / A1 rated |
| RTL-SDR USB dongle | RTL2832U chipset — e.g. RTL-SDR Blog V3, NooElec NESDR |
| 1090 MHz antenna | Dedicated ADS-B antenna gives best range |
| 5V 2.5A power supply | Underpowered supplies cause instability |
| HDMI display (touchscreen or monitor) | 800×480 minimum recommended |

### Optional
| Item | Notes |
|------|-------|
| Official RPi 7" touchscreen | Works plug-and-play |
| Case with fan | Recommended — the Pi 3 runs warm under load |
| USB keyboard | Only needed during initial setup |

### RTL-SDR Dongle Notes
- Buy a **dedicated** ADS-B-band dongle or general-purpose RTL2832U stick
- Avoid cheap no-name dongles — frequency drift causes missed packets
- The RTL-SDR Blog V3 (~£25) is the recommended choice
- The antenna **must** be tuned to 1090 MHz for ADS-B reception
- Position the antenna with a clear sky view — not inside a metal case

---

## 3. Software Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    HARDWARE LAYER                        │
│  RTL-SDR USB dongle  →  1090 MHz RF signals             │
└──────────────────────────┬──────────────────────────────┘
                           │ USB
┌──────────────────────────▼──────────────────────────────┐
│                   dump1090-fa  (systemd)                 │
│  Decodes ADS-B Mode S transponder signals               │
│  Writes /run/dump1090-fa/aircraft.json every 1 sec      │
│  Exposes HTTP on port 30080                             │
└──────────────────────────┬──────────────────────────────┘
                           │ JSON
┌──────────────────────────▼──────────────────────────────┐
│              adsb_backend.py  (Flask, port 5000)         │
│  Reads dump1090 data every 1 sec (background thread)    │
│  Serves /api/aircraft  /api/stats  /api/system          │
│  Serves web interface HTML/CSS/JS at /                  │
└──────────┬────────────────────────────┬─────────────────┘
           │ HTTP API                   │ Static files
┌──────────▼───────────┐   ┌───────────▼─────────────────┐
│  Kivy Dashboard      │   │  Web Interface               │
│  (touchscreen app)   │   │  (Leaflet map, HTML/CSS/JS)  │
│  Reads /api/*        │   │  Served to phones/laptops    │
│  Shows cards + map   │   │  via WiFi hotspot            │
└──────────────────────┘   └─────────────────────────────┘
```

### Why these technology choices?

**Kivy** — best choice for Pi 3 touchscreen apps. Uses OpenGL ES2 directly
(bypasses the heavy desktop stack), has a small footprint (~80 MB RAM), and
handles multi-touch natively. PyQt5 requires X11 and more RAM.

**Flask** — lightweight WSGI framework. Single-file, no ORM overhead, perfect
for a data-relay API on constrained hardware.

**dump1090-fa** — FlightAware's optimised fork of dump1090. Better decoding
algorithm than the original, runs as a proper service, writes JSON natively.

**Leaflet.js** — the gold standard open-source mapping library. Tile-based OSM
maps work offline if tiles are cached. Minimal JS — no heavy frameworks.

**Raspberry Pi OS Lite** — no desktop environment means 150–200 MB less RAM
consumed at idle. We launch exactly what we need, nothing more.

---

## 4. File Structure Reference

```
/opt/adsb-dashboard/
│
├── dashboard/                  ← Kivy touchscreen application
│   ├── main.py                 ← Entry point, Kivy app class
│   ├── screens/
│   │   ├── home.py             ← Main dashboard (4-card layout)
│   │   ├── map.py              ← Map screen (launches Chromium)
│   │   └── settings.py         ← Settings placeholder
│   ├── widgets/
│   │   └── cards.py            ← Card, MetricRow, PrimaryButton, etc.
│   └── utils/
│       ├── theme.py            ← Colour palette, spacing constants
│       ├── sysmetrics.py       ← CPU/RAM/disk/temp readers
│       ├── adsb_client.py      ← dump1090 data reader
│       └── hotspot.py          ← WiFi hotspot manager
│
├── backend/
│   └── adsb_backend.py         ← Flask API server (port 5000)
│
├── web/
│   ├── templates/
│   │   └── index.html          ← Leaflet map web interface
│   └── static/
│       ├── css/style.css       ← Web UI stylesheet
│       └── js/app.js           ← Live aircraft map logic
│
├── config/
│   └── hotspot.json            ← WiFi hotspot settings
│
├── services/                   ← systemd unit files (copied to /etc/systemd/)
│   ├── dump1090-fa.service
│   ├── adsb-backend.service
│   └── adsb-dashboard.service
│
├── scripts/
│   └── install.sh              ← Full installation script
│
└── requirements.txt
```

---

## 5. Installation Guide

### Step 1 — Flash Raspberry Pi OS Lite

1. Download **Raspberry Pi Imager** from raspberrypi.com
2. Insert your microSD card
3. Choose **Raspberry Pi OS Lite (64-bit)** — Bookworm release
4. Click the settings gear icon (⚙) and configure:
   - Hostname: `adsb-radar`
   - Enable SSH: yes
   - Username: `pi`
   - Password: choose a strong password
   - WiFi: set your home network (for initial setup only)
   - Locale: set your timezone
5. Flash the card and insert it into the Pi

### Step 2 — Copy Project Files

Connect to the Pi over SSH or use a USB keyboard:

```bash
# From your computer, copy the project
scp -r adsb-dashboard pi@adsb-radar.local:/home/pi/
```

Or clone from your repository:
```bash
ssh pi@adsb-radar.local
git clone <your-repo-url> /home/pi/adsb-dashboard
```

### Step 3 — Run the Installer

```bash
ssh pi@adsb-radar.local
cd /home/pi/adsb-dashboard
sudo bash scripts/install.sh
```

The installer will:
- Update all system packages
- Install RTL-SDR drivers, dump1090-fa, Chromium, Kivy, Flask
- Deploy all files to `/opt/adsb-dashboard/`
- Install and enable all three systemd services
- Configure autologin and auto-start X
- Configure Openbox to launch the dashboard
- Set GPU memory split to 128 MB
- Add RTL-SDR udev rules
- Blacklist conflicting DVB kernel modules

### Step 4 — Connect Hardware

1. Plug the RTL-SDR dongle into a USB port
2. Connect the 1090 MHz antenna
3. Connect your display via HDMI
4. If using a touchscreen, connect its USB cable (for touch input)

### Step 5 — Reboot

```bash
sudo reboot
```

The Pi will boot and the dashboard will appear within 30–35 seconds.

---

## 6. First Boot & Configuration

### What you see on first boot

1. Linux boots (text scrolls briefly — can be suppressed with splash screen)
2. Autologin triggers for user `pi`
3. X server starts via `startx`
4. Openbox window manager launches
5. Kivy dashboard starts fullscreen
6. After 5–10 seconds, aircraft data appears (if dongle is connected)

### Verify services are running

Open a terminal (SSH in from another computer):

```bash
# Check all three services
sudo systemctl status dump1090-fa
sudo systemctl status adsb-backend
sudo systemctl status adsb-dashboard

# View live logs
sudo journalctl -u dump1090-fa -f
sudo journalctl -u adsb-backend -f
sudo journalctl -u adsb-dashboard -f
```

### Verify dump1090 is receiving

```bash
# Should show aircraft JSON
curl http://localhost:30080/data/aircraft.json | python3 -m json.tool | head -40

# Or check the file directly
cat /run/dump1090-fa/aircraft.json | python3 -m json.tool | head -40
```

### Verify the backend API

```bash
curl http://localhost:5000/api/stats
curl http://localhost:5000/api/aircraft
curl http://localhost:5000/api/system
```

---

## 7. Using the Touchscreen Dashboard

### Header Bar (top, dark background)

| Element | Description |
|---------|-------------|
| `ADS-B RADAR` | Device name (fixed) |
| `HH:MM:SS` | Current time, updates every second |
| `● ADS-B OK` | Green when dump1090 is active and receiving |
| `● ADS-B OFFLINE` | Red when no data received |
| `HOTSPOT ON/OFF` | Current WiFi hotspot state |

### System Information Card (top-left)

Updates every second. Shows:
- **CPU Temp** — °C. Above 80°C indicates poor ventilation
- **CPU Usage** — % across all cores
- **RAM** — used / total in MB
- **Storage** — used / total in GB
- **Uptime** — time since last boot
- **Msg/sec** — ADS-B messages decoded per second (typical: 100–1000)
- **Tracked** — number of aircraft currently being tracked

### WiFi Hotspot Card (top-right)

- Shows current SSID and IP address
- Tap **ENABLE HOTSPOT** to start the WiFi access point
  - The button changes to **DISABLE HOTSPOT** (red)
  - Status shows `Hotspot Active — 192.168.4.1`
- Tap **DISABLE HOTSPOT** to stop it
- Toggle takes 3–8 seconds — a "PLEASE WAIT" message appears
- **Note:** Enabling the hotspot disconnects the Pi from your home WiFi

### ADS-B Map Card (bottom-left)

- Shows total aircraft count and how many have position data
- Tap **OPEN MAP** to launch the Chromium browser in kiosk mode
  - The browser opens fullscreen showing the Leaflet map
  - Tap the **◀ BACK** button in the top bar to return to the dashboard
  - The browser closes automatically when you go back

### Settings Card (bottom-right)

Reserved for future expansion. No functionality in v1.0.

---

## 8. Using the Web Interface

### Accessing the web interface

**When hotspot is active:**
1. Connect your phone/laptop to the `ADSB-RADAR` WiFi network
2. Password: `aircraft123` (change this — see Configuration Files)
3. Open a browser and go to `http://192.168.4.1`

**From the same network as the Pi:**
- Find the Pi's IP address: `hostname -I`
- Navigate to `http://<pi-ip-address>:5000`

### Web interface layout

**Header bar** — Device name, live clock, ADS-B status badge, aircraft count

**Left sidebar:**
- Aircraft count
- Mini system stats (CPU temp, RAM, message rate)
- Live scrollable aircraft list — sorted by altitude (highest first)
- Click any aircraft in the list to pan the map to it and open its popup

**Main map area:**
- OpenStreetMap tiles via Leaflet
- Blue aircraft icons pointing in the direction of travel
- Labels show callsign above each aircraft
- Click any aircraft icon to open its information popup

**Aircraft popup shows:**
- ICAO hex code
- Callsign (flight number)
- Altitude in feet
- Ground speed in knots
- Heading in degrees
- Squawk code
- Signal strength (RSSI in dBFS)

### Live update behaviour

- Aircraft positions refresh every **1 second**
- System stats refresh every **5 seconds**
- Aircraft that haven't been heard for 60 seconds are removed from the map
- Aircraft heard 30–60 seconds ago are shown in grey (stale)
- The map auto-centres on the first aircraft with position data on load

---

## 9. WiFi Hotspot Setup

### Default credentials

| Setting | Value |
|---------|-------|
| SSID | `ADSB-RADAR` |
| Password | `aircraft123` |
| Pi IP (gateway) | `192.168.4.1` |
| DHCP range | `192.168.4.2` – `192.168.4.20` |
| Channel | 6 (2.4 GHz) |

### Changing SSID and password

Edit the config file:
```bash
sudo nano /opt/adsb-dashboard/config/hotspot.json
```

```json
{
  "ssid": "YOUR-SSID",
  "password": "yourpassword",
  "channel": 6,
  "interface": "wlan0",
  "ip": "192.168.4.1"
}
```

Restart the system or toggle the hotspot off/on via the dashboard.

### How the hotspot works

The system uses **NetworkManager** (nmcli) if available (Bookworm default),
falling back to direct **hostapd + dnsmasq** configuration.

When enabled:
1. The `wlan0` interface is configured as an Access Point
2. A DHCP server assigns addresses in the `192.168.4.x` range
3. Connecting clients can reach the web interface at `http://192.168.4.1`
4. The Pi's home WiFi connection is suspended while the hotspot is active

### Important limitation

The RPi 3 has a **single WiFi chip** (BCM43438). It cannot simultaneously
connect to your home network AND run a hotspot. When the hotspot is on,
internet access via WiFi is not available. If you need both, add a USB WiFi
adapter and configure it to use `wlan1`.

---

## 10. System Services Reference

Three systemd services run in order:

### dump1090-fa
- **Purpose:** Decodes ADS-B radio signals from the RTL-SDR dongle
- **Port:** HTTP on 30080 (aircraft data), TCP/30001-30005 (Beast/SBS formats)
- **Output:** Writes `/run/dump1090-fa/aircraft.json` every 1 second
- **Restart policy:** Always restarts on failure, 5-second delay

```bash
sudo systemctl start/stop/restart dump1090-fa
sudo journalctl -u dump1090-fa -f
```

### adsb-backend
- **Purpose:** Python/Flask API that reads dump1090 and serves JSON + web UI
- **Port:** 5000
- **Endpoints:** `/api/aircraft`, `/api/stats`, `/api/system`, `/api/health`
- **RAM limit:** 128 MB

```bash
sudo systemctl start/stop/restart adsb-backend
sudo journalctl -u adsb-backend -f
```

### adsb-dashboard
- **Purpose:** Kivy touchscreen application (the card dashboard)
- **Requires:** X display on `:0` (started by autologin → startx)
- **RAM limit:** 200 MB

```bash
sudo systemctl start/stop/restart adsb-dashboard
sudo journalctl -u adsb-dashboard -f
```

### Service startup order

```
System boot
    → autologin (getty@tty1)
    → startx (xinit)
    → openbox
    → dump1090-fa  (systemd, starts early)
    → adsb-backend (starts after dump1090-fa)
    → adsb-dashboard (started by openbox autostart)
```

---

## 11. Configuration Files

### `/opt/adsb-dashboard/config/hotspot.json`
WiFi hotspot settings. Edit and toggle hotspot to apply.

### `/boot/config.txt` (Raspberry Pi boot config)
The installer adds:
```
gpu_mem=128          # 128 MB GPU memory for Kivy OpenGL
hdmi_force_hotplug=1 # Force HDMI even without display at boot
```

For a touchscreen (e.g. official RPi 7" display), also add:
```
display_rotate=0     # 0=normal, 1=90°, 2=180°, 3=270°
```

### `/home/pi/.config/openbox/autostart`
Commands run by Openbox on X startup:
```bash
xset s off &         # No screen saver
xset -dpms &         # No display power management
xset s noblank &     # No blank screen
unclutter -idle 1 &  # Hide cursor after 1 second
python3 /opt/adsb-dashboard/dashboard/main.py &
```

### `/etc/modprobe.d/rtlsdr-blacklist.conf`
Prevents Linux DVB drivers from claiming the RTL-SDR device:
```
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
```

---

## 12. Troubleshooting

### No aircraft appearing

**Check 1 — Is the dongle detected?**
```bash
lsusb | grep -i realtek
# Should show: Bus 00x Device 00x: ID 0bda:2838 Realtek Semiconductor Corp.
```

**Check 2 — Is dump1090 running?**
```bash
sudo systemctl status dump1090-fa
# Look for "active (running)"
```

**Check 3 — Is the dongle being used by the DVB driver?**
```bash
lsmod | grep dvb
# If this shows anything, the blacklist didn't apply. Reboot.
```

**Check 4 — Is the antenna connected?**
Without an antenna, reception range is approximately 0–5 km. You need aircraft
overhead to test without an antenna.

**Check 5 — Test dump1090 manually**
```bash
sudo systemctl stop dump1090-fa
dump1090-fa --interactive
# You should see aircraft scrolling past if any are in range
```

### Dashboard doesn't appear on screen

**Check 1 — Is X running?**
```bash
ps aux | grep xinit
# Should show an xinit/Xorg process
```

**Check 2 — Kivy log**
```bash
sudo journalctl -u adsb-dashboard -n 50
```

**Check 3 — Run dashboard manually**
```bash
sudo -u pi DISPLAY=:0 python3 /opt/adsb-dashboard/dashboard/main.py
```

**Check 4 — Kivy not installed**
```bash
python3 -c "import kivy; print(kivy.__version__)"
# Should print 2.3.0
```

### Web interface not loading

**Check 1 — Backend running?**
```bash
curl http://localhost:5000/api/health
# Should return: {"status": "ok", ...}
```

**Check 2 — Port in use?**
```bash
sudo ss -tlnp | grep 5000
```

**Check 3 — Flask not installed?**
```bash
python3 -c "import flask; print(flask.__version__)"
```

### Hotspot won't start

**Check — NetworkManager status**
```bash
nmcli general status
nmcli con show
```

**Manual test**
```bash
sudo nmcli con add type wifi ifname wlan0 con-name test-ap ssid TEST-AP \
  -- wifi.mode ap wifi-sec.key-mgmt wpa-psk wifi-sec.psk testpass123 \
  ipv4.method shared
sudo nmcli con up test-ap
```

### High CPU temperature

- Ensure the Pi has adequate airflow — the SoC reaches 80°C under load
- Add a heatsink to the CPU (cheap, effective)
- Add a small fan if temperature regularly exceeds 80°C
- Check `vcgencmd measure_temp` for real-time temperature

### Map shows no tiles (grey squares)

The web interface requires internet access to load OpenStreetMap tiles.
On the hotspot without internet, tiles won't load.

**Solution:** Pre-cache tiles using a tile caching proxy (future upgrade).
For now, the aircraft markers still appear even without tiles.

---

## 13. Security Notes

This system is designed for a **private/local network**. It is not hardened
for exposure to the public internet. Key points:

- **Change the default hotspot password** (`aircraft123`) before use
- The Flask API has no authentication — don't expose port 5000 externally
- SSH is enabled — use key-based authentication:
  ```bash
  ssh-copy-id pi@adsb-radar.local
  sudo nano /etc/ssh/sshd_config
  # Set: PasswordAuthentication no
  sudo systemctl restart ssh
  ```
- The `pi` user has sudo access — restrict if deploying in a shared space
- RTL-SDR access is granted to the `plugdev` group — only add trusted users

---

## 14. Future Upgrades

The Settings card is reserved. Planned expansion:

### Short term
- Configurable SSID/password via touchscreen keyboard
- Brightness control for the display
- Offline tile caching for the map
- Aircraft history trails (last N positions)
- Alert when specific squawk codes are seen (7700 emergency, 7500 hijack)

### Medium term
- MLAT (Multilateration) via piaware/FR24 feeder
- Feed to FlightAware / FlightRadar24 / ADSBExchange
- Aircraft database lookup (ICAO → registration → aircraft type)
- Aircraft type icons (narrow-body, wide-body, helicopter, etc.)
- Export to GPX/KML for range mapping

### Long term
- Second RTL-SDR for UAT 978 MHz (US domestic low-altitude traffic)
- VRS (Virtual Radar Server) integration
- Push notifications for interesting aircraft
- Web-based configuration panel
- Docker containerisation for easier updates

---

## 15. Technology Decisions Explained

### Why Kivy over PyQt?

| Factor | Kivy | PyQt5 |
|--------|------|-------|
| GPU acceleration | Direct OpenGL ES2 | Requires full Qt stack |
| RAM usage | ~80 MB | ~150–200 MB |
| X11 dependency | Optional (can use SDL2) | Required |
| Touch input | Native multi-touch | Requires extra config |
| RPi 3 performance | Smooth at 800×480 | Can feel sluggish |
| Python version | 3.x native | 3.x native |

Kivy renders everything through OpenGL ES2, using the Pi's VideoCore IV GPU.
This gives smooth 60 fps on the dashboard. PyQt renders through X11's software
path on the Pi, which is noticeably slower for animated content.

### Why Flask over FastAPI/Django?

Flask is a single-file WSGI app with zero ORM overhead. On a Pi 3 with 1 GB
RAM serving local clients, FastAPI's async overhead isn't useful. Flask starts
in under 1 second and uses ~25 MB RAM idle. It's the right tool for a simple
data relay API.

### Why dump1090-fa over readsb or others?

dump1090-fa (FlightAware's fork) has:
- The best Mode S decoding algorithm in the open-source space
- JSON output with all fields we need
- Proper systemd service packaging
- Active maintenance by FlightAware engineers
- Proven stability — runs on millions of Pi feeders worldwide

### Why Leaflet over Mapbox GL / Google Maps?

- Open source, no API key required
- Works with OpenStreetMap tiles (free, no usage limits)
- Extremely lightweight (~42 KB gzipped)
- Excellent mobile touch support
- Well-documented custom marker API
- Can work offline with cached tiles (future feature)

### Why Raspberry Pi OS Lite over full desktop?

The full desktop (PIXEL/LXDE) consumes ~350–400 MB RAM at idle and loads
dozens of background services we don't need. Pi OS Lite boots to a shell in
~15 seconds using ~150 MB RAM, leaving maximum memory for the dashboard,
backend, and dump1090.

We add only Openbox (a minimal window manager, ~5 MB) to manage our single
fullscreen window. The total overhead of the desktop layer is under 30 MB.

---

*ADS-B RADAR v1.0 — Built for Raspberry Pi 3*
