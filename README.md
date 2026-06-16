# ADS-B RADAR 📡

A Raspberry Pi 3 ADS-B receiver appliance. Boots directly into a fullscreen
touchscreen dashboard. No desktop. No keyboard required.

```
RTL-SDR dongle → dump1090-fa → Python backend → Kivy touchscreen dashboard
                                              → Web interface (Leaflet map)
```

## Hardware needed

- Raspberry Pi 3 Model B or B+
- RTL-SDR USB dongle (RTL2832U chipset)
- 1090 MHz ADS-B antenna
- HDMI touchscreen or monitor (800×480 minimum)
- 16 GB+ microSD card
- 5V 2.5A power supply

## Quick install (one command)

```bash
git clone https://github.com/will-coleman/flightbankmini.git
cd flightbankmini
sudo bash scripts/install.sh
sudo reboot
```

See [MANUAL.md](MANUAL.md) for full documentation.

## What it does

- Decodes ADS-B aircraft transponders within ~200–350 km
- Fullscreen Kivy dashboard: system stats, aircraft count, WiFi hotspot toggle
- WiFi hotspot (SSID: `ADSB-RADAR`) so phones/laptops can view the map
- Web interface at `http://192.168.4.1` — live Leaflet map with aircraft list
- All three services auto-start on boot via systemd

## Default hotspot

| | |
|---|---|
| SSID | `ADSB-RADAR` |
| Password | `aircraft123` |
| Web UI | `http://192.168.4.1` |

**Change the password** in `config/hotspot.json` before use.

## Project layout

```
dashboard/    Kivy touchscreen app
backend/      Flask JSON API (port 5000)
web/          Leaflet web interface
services/     systemd unit files
scripts/      install.sh
config/       hotspot.json (gitignored — copy from hotspot.json.example)
```

## License

MIT
