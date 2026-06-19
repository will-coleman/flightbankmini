#!/usr/bin/env python3
"""
download_tiles.py — Fetch map tiles for OFFLINE use.

Uses Geoapify, whose tile policy explicitly permits caching/storing tiles
offline (unlike OpenStreetMap's public servers, which block bulk pulls).

  1. Get a FREE API key at https://www.geoapify.com/  (no card needed)
  2. Paste it into GEOAPIFY_KEY below.
  3. Run this ONCE on a machine with internet (your Mac is easiest):
         python3 download_tiles.py ./tiles
     then copy the folder to the Pi (see README / chat for scp command).
     Or run it on the Pi itself if it has internet (Ethernet).

Tiles are saved as  <out_dir>/{z}/{x}/{y}.png  and served by Leaflet at
/static/tiles/{z}/{x}/{y}.png — no internet needed when viewing.
"""

import math
import os
import sys
import time
import urllib.request

# -- Geoapify API key ------------------------------------------------------
# Free key from https://www.geoapify.com/  ->  create a project  ->  copy key.
GEOAPIFY_KEY = 'f1e8902f310d47f68d277c8f138867dd'

# Map style. Options: osm-bright, osm-carto, klokantech-basic,
# positron, dark-matter, toner. 'osm-bright' is a good general-purpose look.
STYLE = 'osm-bright'

# -- Coverage area — southern England / ADS-B reception range --------------
NORTH =  53.2
SOUTH =  49.3
WEST  =  -3.8
EAST  =   2.2

MIN_ZOOM = 6     # wide regional view
MAX_ZOOM = 11    # close enough to see individual towns

# -- Tile source -----------------------------------------------------------
TILE_URL = ('https://maps.geoapify.com/v1/tile/' + STYLE +
            '/{z}/{x}/{y}.png?apiKey=' + GEOAPIFY_KEY)
USER_AGENT = 'FBRadarMINI-offline-tiles/1.0 (personal ADS-B appliance)'
DELAY = 0.05

# -- Output directory ------------------------------------------------------
if len(sys.argv) > 1:
    OUT_DIR = sys.argv[1]
else:
    OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', 'web', 'static', 'tiles')
OUT_DIR = os.path.abspath(OUT_DIR)


def deg2num(lat, lon, z):
    lat_r = math.radians(lat)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def build_jobs():
    jobs = []
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        x0, y0 = deg2num(NORTH, WEST, z)
        x1, y1 = deg2num(SOUTH, EAST, z)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                jobs.append((z, x, y))
    return jobs


def main():
    if GEOAPIFY_KEY == 'YOUR_KEY_HERE' or not GEOAPIFY_KEY.strip():
        print("ERROR: set GEOAPIFY_KEY near the top of this file first.")
        print("Get a free key at https://www.geoapify.com/")
        sys.exit(1)

    jobs = build_jobs()
    print(f"Output dir : {OUT_DIR}")
    print(f"Style      : {STYLE}")
    print(f"Tiles to fetch: {len(jobs)} (zoom {MIN_ZOOM}-{MAX_ZOOM})")
    os.makedirs(OUT_DIR, exist_ok=True)

    done = skipped = failed = 0
    for (z, x, y) in jobs:
        done += 1
        d = os.path.join(OUT_DIR, str(z), str(x))
        os.makedirs(d, exist_ok=True)
        fpath = os.path.join(d, f"{y}.png")

        if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
            skipped += 1
            continue

        url = TILE_URL.format(z=z, x=x, y=y)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            with open(fpath, 'wb') as f:
                f.write(data)
            time.sleep(DELAY)
        except Exception as e:
            failed += 1
            print(f"  FAILED {z}/{x}/{y}: {e}")
            time.sleep(1)

        if done % 50 == 0:
            print(f"  {done}/{len(jobs)}  (skipped {skipped}, failed {failed})")

    # 1x1 transparent PNG used by Leaflet for any missing tile
    blank = os.path.join(OUT_DIR, 'blank.png')
    if not os.path.exists(blank):
        png = bytes.fromhex(
            '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
            '890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082'
        )
        with open(blank, 'wb') as f:
            f.write(png)

    print(f"\nDone. fetched {done - skipped - failed}, "
          f"skipped {skipped}, failed {failed}.")
    print("Tiles are served at /static/tiles/{z}/{x}/{y}.png")


if __name__ == '__main__':
    main()

