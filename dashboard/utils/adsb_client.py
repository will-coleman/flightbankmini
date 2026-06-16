"""
ADS-B data client.
Reads aircraft.json from dump1090-fa (local socket or file).
Also queries the backend API for aggregated stats.
"""

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import List, Optional, Dict


DUMP1090_AIRCRAFT_URL  = 'http://127.0.0.1:30080/data/aircraft.json'
DUMP1090_AIRCRAFT_FILE = '/run/dump1090-fa/aircraft.json'
BACKEND_STATS_URL      = 'http://127.0.0.1:5000/api/stats'


@dataclass
class Aircraft:
    icao:      str
    callsign:  str       = ''
    lat:       Optional[float] = None
    lon:       Optional[float] = None
    altitude:  Optional[int]   = None    # feet
    speed:     Optional[float] = None    # knots
    heading:   Optional[float] = None    # degrees
    vert_rate: Optional[int]   = None    # ft/min
    squawk:    str             = ''
    rssi:      Optional[float] = None
    seen:      float           = 0.0
    messages:  int             = 0

    @property
    def has_position(self) -> bool:
        return self.lat is not None and self.lon is not None

    @property
    def altitude_str(self) -> str:
        if self.altitude is None:
            return '—'
        if self.altitude == 0:
            return 'Ground'
        return f"{self.altitude:,} ft"

    @property
    def speed_str(self) -> str:
        return f"{int(self.speed)} kt" if self.speed is not None else '—'


@dataclass
class ADSBStats:
    aircraft_total:    int = 0
    aircraft_with_pos: int = 0
    messages_rate:     float = 0.0   # msgs/sec
    messages_total:    int = 0


def _fetch_json(url: str, timeout: float = 1.5) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _read_aircraft_file() -> Optional[dict]:
    try:
        with open(DUMP1090_AIRCRAFT_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def fetch_aircraft() -> List[Aircraft]:
    """
    Fetch aircraft list from dump1090.
    Tries HTTP first (dump1090-fa web port), falls back to file.
    """
    data = _fetch_json(DUMP1090_AIRCRAFT_URL) or _read_aircraft_file()
    if not data:
        return []

    result = []
    for ac in data.get('aircraft', []):
        # Ignore stale entries (not seen in last 60 seconds)
        if ac.get('seen', 999) > 60:
            continue

        aircraft = Aircraft(
            icao=ac.get('hex', '').upper(),
            callsign=(ac.get('flight', '') or '').strip(),
            lat=ac.get('lat'),
            lon=ac.get('lon'),
            altitude=_coerce_int(ac.get('alt_baro') or ac.get('altitude')),
            speed=ac.get('gs') or ac.get('speed'),
            heading=ac.get('track') or ac.get('heading'),
            vert_rate=_coerce_int(ac.get('baro_rate') or ac.get('vert_rate')),
            squawk=ac.get('squawk', ''),
            rssi=ac.get('rssi'),
            seen=ac.get('seen', 0),
            messages=ac.get('messages', 0),
        )
        result.append(aircraft)

    return result


def fetch_stats() -> ADSBStats:
    """Fetch aggregated statistics from backend API, or compute locally."""
    data = _fetch_json(BACKEND_STATS_URL)
    if data:
        return ADSBStats(
            aircraft_total=data.get('aircraft_total', 0),
            aircraft_with_pos=data.get('aircraft_with_pos', 0),
            messages_rate=data.get('messages_rate', 0.0),
            messages_total=data.get('messages_total', 0),
        )

    # Fallback: compute from local aircraft list
    aircraft = fetch_aircraft()
    return ADSBStats(
        aircraft_total=len(aircraft),
        aircraft_with_pos=sum(1 for a in aircraft if a.has_position),
        messages_rate=0.0,
        messages_total=0,
    )


def _coerce_int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
