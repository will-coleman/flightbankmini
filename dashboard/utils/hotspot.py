"""
WiFi Hotspot Manager
Controls the Raspberry Pi access point via NetworkManager (nmcli).
Falls back to direct hostapd/dnsmasq control if NM is absent.
"""

import subprocess
import os
import json
from pathlib import Path


CONFIG_FILE = '/opt/adsb-dashboard/config/hotspot.json'

DEFAULT_CONFIG = {
    'ssid': 'ADSB-RADAR',
    'password': 'aircraft123',
    'channel': 6,
    'interface': 'wlan0',
    'ip': '192.168.4.1',
}


def _run(cmd: list, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
            return {**DEFAULT_CONFIG, **cfg}
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    Path(CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def is_hotspot_active() -> bool:
    """Return True if the AP connection is active."""
    # Check NetworkManager
    r = _run(['nmcli', '-t', '-f', 'TYPE,STATE', 'con', 'show', '--active'])
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if '802-11-wireless' in line and 'activated' in line:
                # Verify it's in AP mode
                r2 = _run(['nmcli', '-t', '-f', 'WIFI-PROPERTIES.MODE', 'dev', 'show', 'wlan0'])
                if 'AP' in r2.stdout:
                    return True

    # Fallback: check hostapd
    r = _run(['systemctl', 'is-active', 'hostapd'])
    return r.stdout.strip() == 'active'


def start_hotspot(ssid: str, password: str) -> tuple:
    """
    Start WiFi hotspot. Returns (success: bool, message: str).
    Uses NetworkManager if available, else falls back to hostapd.
    """
    cfg = load_config()
    cfg['ssid'] = ssid
    cfg['password'] = password
    save_config(cfg)

    # Try NetworkManager first
    r = _run(['which', 'nmcli'])
    if r.returncode == 0:
        return _start_hotspot_nm(cfg)
    else:
        return _start_hotspot_hostapd(cfg)


def stop_hotspot() -> tuple:
    """Stop WiFi hotspot. Returns (success: bool, message: str)."""
    r = _run(['which', 'nmcli'])
    if r.returncode == 0:
        return _stop_hotspot_nm()
    else:
        return _stop_hotspot_hostapd()


def _start_hotspot_nm(cfg: dict) -> tuple:
    """Start AP using NetworkManager hotspot connection."""
    iface = cfg['interface']
    ssid = cfg['ssid']
    password = cfg['password']

    # Remove existing hotspot connection if present
    _run(['nmcli', 'con', 'delete', 'ADSB-Hotspot'])

    # Create new hotspot connection
    r = _run([
        'nmcli', 'con', 'add',
        'type', 'wifi',
        'ifname', iface,
        'con-name', 'ADSB-Hotspot',
        'autoconnect', 'no',
        'ssid', ssid,
        '--', 'wifi.mode', 'ap',
        'wifi-sec.key-mgmt', 'wpa-psk',
        'wifi-sec.psk', password,
        'ipv4.method', 'shared',
        'ipv4.addresses', f"{cfg['ip']}/24",
    ])

    if r.returncode != 0:
        return False, f"Failed to create connection: {r.stderr.strip()}"

    r = _run(['nmcli', 'con', 'up', 'ADSB-Hotspot'])
    if r.returncode != 0:
        return False, f"Failed to activate hotspot: {r.stderr.strip()}"

    return True, 'Hotspot active'


def _stop_hotspot_nm() -> tuple:
    r = _run(['nmcli', 'con', 'down', 'ADSB-Hotspot'])
    if r.returncode != 0:
        return False, f"Failed to stop: {r.stderr.strip()}"
    return True, 'Hotspot stopped'


def _start_hotspot_hostapd(cfg: dict) -> tuple:
    """Fallback: configure and start hostapd + dnsmasq directly."""
    try:
        _write_hostapd_conf(cfg)
        _write_dnsmasq_conf(cfg)

        # Bring up wlan0 with static IP
        _run(['ip', 'addr', 'flush', 'dev', cfg['interface']])
        _run(['ip', 'addr', 'add', f"{cfg['ip']}/24", 'dev', cfg['interface']])
        _run(['ip', 'link', 'set', cfg['interface'], 'up'])

        r1 = _run(['systemctl', 'restart', 'hostapd'])
        r2 = _run(['systemctl', 'restart', 'dnsmasq'])

        if r1.returncode != 0 or r2.returncode != 0:
            return False, 'hostapd/dnsmasq failed to start'

        return True, 'Hotspot active (hostapd)'
    except Exception as e:
        return False, str(e)


def _stop_hotspot_hostapd() -> tuple:
    _run(['systemctl', 'stop', 'hostapd'])
    _run(['systemctl', 'stop', 'dnsmasq'])
    return True, 'Hotspot stopped'


def _write_hostapd_conf(cfg: dict):
    content = f"""interface={cfg['interface']}
driver=nl80211
ssid={cfg['ssid']}
hw_mode=g
channel={cfg['channel']}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={cfg['password']}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
    with open('/etc/hostapd/hostapd.conf', 'w') as f:
        f.write(content)


def _write_dnsmasq_conf(cfg: dict):
    iface = cfg['interface']
    ip_prefix = '.'.join(cfg['ip'].split('.')[:3])
    content = f"""interface={iface}
dhcp-range={ip_prefix}.2,{ip_prefix}.20,255.255.255.0,24h
domain=local
address=/adsb.local/{cfg['ip']}
"""
    with open('/etc/dnsmasq.conf', 'w') as f:
        f.write(content)
