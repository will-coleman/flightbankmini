#!/usr/bin/env python3
"""
ADS-B Backend API  —  adsb_backend.py
Runs as a systemd service on port 5000.
Serves:
  GET /              → web interface (Leaflet map)
  GET /api/aircraft  → live aircraft list
  GET /api/stats     → ADS-B + system statistics
  GET /api/system    → system metrics only
"""

import os
import json
import time
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, send_from_directory, Response

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path('/opt/adsb-dashboard')
WEB_DIR    = BASE_DIR / 'web'
STATIC_DIR = WEB_DIR / 'static'

# Primary: dump1090 HTTP API (if available)
# Fallback: JSON file written by --write-json flag
DUMP1090_URL  = 'http://127.0.0.1:8080/data/aircraft.json'
DUMP1090_FILE = '/run/dump1090-fa/aircraft.json'

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path='/static')

# ── In-memory state updated by background thread ───────────────────────────
_state_lock = threading.Lock()
_state = {
    'aircraft':          [],
    'aircraft_total':    0,
    'aircraft_with_pos': 0,
    'messages_rate':     0.0,
    'messages_total':    0,
    'last_updated':      None,
    'dump1090_ok':       False,
}

# ── dump1090 poller ────────────────────────────────────────────────────────

def _read_dump1090():
    """Try HTTP API then fall back to JSON file written by --write-json."""
    try:
        req = urllib.request.Request(DUMP1090_URL,
                                     headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        pass
    try:
        with open(DUMP1090_FILE) as f:
            return json.load(f)
    except Exception:
        return None


_prev_msg_count = 0
_prev_msg_time  = time.time()


def _poll_loop():
    global _prev_msg_count, _prev_msg_time
    while True:
        try:
            data = _read_dump1090()
            if data:
                aircraft_raw = data.get('aircraft', [])
                now = time.time()

                # Filter stale (>60 s)
                fresh = [a for a in aircraft_raw if a.get('seen', 999) <= 60]

                # Message rate
                total_msgs = sum(a.get('messages', 0) for a in fresh)
                elapsed    = now - _prev_msg_time
                rate = (total_msgs - _prev_msg_count) / elapsed if elapsed > 0 else 0.0
                _prev_msg_count = total_msgs
                _prev_msg_time  = now

                # Normalise aircraft records
                normalised = []
                for a in fresh:
                    normalised.append({
                        'icao':      a.get('hex', '').upper(),
                        'callsign':  (a.get('flight') or '').strip(),
                        'lat':       a.get('lat'),
                        'lon':       a.get('lon'),
                        'altitude':  _safe_int(a.get('alt_baro') or a.get('altitude')),
                        'speed':     a.get('gs') or a.get('speed'),
                        'heading':   a.get('track') or a.get('heading'),
                        'vert_rate': _safe_int(a.get('baro_rate') or a.get('vert_rate')),
                        'squawk':    a.get('squawk', ''),
                        'rssi':      a.get('rssi'),
                        'seen':      a.get('seen', 0),
                        'messages':  a.get('messages', 0),
                    })

                with_pos = sum(1 for a in normalised
                               if a['lat'] is not None and a['lon'] is not None)

                with _state_lock:
                    _state['aircraft']           = normalised
                    _state['aircraft_total']     = len(normalised)
                    _state['aircraft_with_pos']  = with_pos
                    _state['messages_rate']      = round(max(rate, 0.0), 1)
                    _state['messages_total']     = total_msgs
                    _state['last_updated']       = datetime.utcnow().isoformat() + 'Z'
                    _state['dump1090_ok']        = True
            else:
                with _state_lock:
                    _state['dump1090_ok'] = False
        except Exception:
            with _state_lock:
                _state['dump1090_ok'] = False

        time.sleep(1.0)


def _safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ── System metrics ─────────────────────────────────────────────────────────

def _get_system_metrics():
    metrics = {}

    # CPU temp
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            metrics['cpu_temp_c'] = round(int(f.read()) / 1000, 1)
    except Exception:
        metrics['cpu_temp_c'] = None

    # Memory
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                k, v = line.split(':')
                info[k.strip()] = int(v.split()[0])
        total = info['MemTotal']
        avail = info.get('MemAvailable', info.get('MemFree', 0))
        used  = total - avail
        metrics['ram_total_mb'] = round(total / 1024, 1)
        metrics['ram_used_mb']  = round(used  / 1024, 1)
        metrics['ram_percent']  = round(100 * used / total, 1)
    except Exception:
        metrics.update(ram_total_mb=None, ram_used_mb=None, ram_percent=None)

    # Uptime
    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
        metrics['uptime_seconds'] = secs
        metrics['uptime_str']     = f"{secs//3600:02d}h {(secs%3600)//60:02d}m"
    except Exception:
        metrics['uptime_seconds'] = 0
        metrics['uptime_str']     = '—'

    # Disk
    try:
        st = os.statvfs('/')
        total_b = st.f_frsize * st.f_blocks
        free_b  = st.f_frsize * st.f_bavail
        used_b  = total_b - free_b
        metrics['disk_total_gb'] = round(total_b / 1e9, 1)
        metrics['disk_used_gb']  = round(used_b  / 1e9, 1)
        metrics['disk_percent']  = round(100 * used_b / total_b, 1)
    except Exception:
        metrics.update(disk_total_gb=None, disk_used_gb=None, disk_percent=None)

    return metrics


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(str(WEB_DIR / 'templates'), 'index.html')


@app.route('/api/aircraft')
def api_aircraft():
    with _state_lock:
        data = {
            'aircraft':    _state['aircraft'],
            'total':       _state['aircraft_total'],
            'with_pos':    _state['aircraft_with_pos'],
            'dump1090_ok': _state['dump1090_ok'],
            'timestamp':   _state['last_updated'],
        }
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/api/stats')
def api_stats():
    with _state_lock:
        data = {
            'aircraft_total':    _state['aircraft_total'],
            'aircraft_with_pos': _state['aircraft_with_pos'],
            'messages_rate':     _state['messages_rate'],
            'messages_total':    _state['messages_total'],
            'dump1090_ok':       _state['dump1090_ok'],
            'last_updated':      _state['last_updated'],
        }
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/system')
def api_system():
    resp = jsonify(_get_system_metrics())
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'ts': datetime.utcnow().isoformat()})


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
