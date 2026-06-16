"""
System metrics collection for Raspberry Pi.
Uses /proc and /sys to avoid heavy dependencies.
"""

import os
import time
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemMetrics:
    cpu_temp: float        # °C
    cpu_usage: float       # %
    ram_used_mb: float
    ram_total_mb: float
    ram_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    uptime_seconds: int
    uptime_str: str


def read_cpu_temp() -> float:
    """Read CPU temperature from sysfs."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return 0.0


_prev_cpu_times = None

def read_cpu_usage() -> float:
    """Calculate CPU usage % between calls."""
    global _prev_cpu_times

    def _read_stat():
        with open('/proc/stat') as f:
            line = f.readline()
        parts = line.split()
        # user, nice, system, idle, iowait, irq, softirq
        vals = [int(p) for p in parts[1:8]]
        total = sum(vals)
        idle = vals[3] + vals[4]  # idle + iowait
        return total, idle

    try:
        cur_total, cur_idle = _read_stat()
        if _prev_cpu_times is None:
            _prev_cpu_times = (cur_total, cur_idle)
            return 0.0
        prev_total, prev_idle = _prev_cpu_times
        _prev_cpu_times = (cur_total, cur_idle)
        d_total = cur_total - prev_total
        d_idle = cur_idle - prev_idle
        if d_total == 0:
            return 0.0
        return round(100.0 * (1.0 - d_idle / d_total), 1)
    except Exception:
        return 0.0


def read_memory() -> tuple:
    """Return (used_mb, total_mb, percent)."""
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(':')] = int(parts[1])
        total_kb = info.get('MemTotal', 0)
        avail_kb = info.get('MemAvailable', 0)
        used_kb  = total_kb - avail_kb
        total_mb = total_kb / 1024
        used_mb  = used_kb  / 1024
        pct = round(100.0 * used_mb / total_mb, 1) if total_mb else 0.0
        return used_mb, total_mb, pct
    except Exception:
        return 0.0, 0.0, 0.0


def read_disk(path='/') -> tuple:
    """Return (used_gb, total_gb, percent)."""
    try:
        st = os.statvfs(path)
        total = st.f_frsize * st.f_blocks
        free  = st.f_frsize * st.f_bavail
        used  = total - free
        total_gb = total / 1e9
        used_gb  = used  / 1e9
        pct = round(100.0 * used_gb / total_gb, 1) if total_gb else 0.0
        return used_gb, total_gb, pct
    except Exception:
        return 0.0, 0.0, 0.0


def read_uptime() -> tuple:
    """Return (seconds, human_string)."""
    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
        days    = secs // 86400
        hours   = (secs % 86400) // 3600
        minutes = (secs % 3600)  // 60
        if days:
            label = f"{days}d {hours:02d}h {minutes:02d}m"
        else:
            label = f"{hours:02d}h {minutes:02d}m"
        return secs, label
    except Exception:
        return 0, '00h 00m'


def get_metrics() -> SystemMetrics:
    used_mb, total_mb, ram_pct = read_memory()
    used_gb, total_gb, disk_pct = read_disk()
    uptime_secs, uptime_str = read_uptime()

    return SystemMetrics(
        cpu_temp=read_cpu_temp(),
        cpu_usage=read_cpu_usage(),
        ram_used_mb=used_mb,
        ram_total_mb=total_mb,
        ram_percent=ram_pct,
        disk_used_gb=used_gb,
        disk_total_gb=total_gb,
        disk_percent=disk_pct,
        uptime_seconds=uptime_secs,
        uptime_str=uptime_str,
    )
