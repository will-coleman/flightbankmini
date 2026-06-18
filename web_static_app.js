/**
 * ADS-B RADAR  —  Web Frontend
 * Leaflet map with live aircraft positions from /api/aircraft
 * Refresh: 1 second
 *
 * Map tiles are served LOCALLY from /static/tiles (offline — no internet
 * needed). Download them first with scripts/download_tiles.py.
 */

'use strict';

// ── Config ──────────────────────────────────────────────────────────────
const REFRESH_MS   = 1000;
const API_AIRCRAFT = '/api/aircraft';
const API_STATS    = '/api/stats';
const API_SYSTEM   = '/api/system';

// Default centre — Heathrow. Will move to first aircraft with position.
const DEFAULT_LAT = 51.477;
const DEFAULT_LON = -0.461;
const DEFAULT_ZOOM = 8;

// Must match the zoom range downloaded by download_tiles.py
const MIN_ZOOM = 6;
const MAX_ZOOM = 11;

// ── State ───────────────────────────────────────────────────────────────
const markers = {};          // icao → { marker, label }
let selectedIcao = null;
let mapCentred   = false;

// ── Map init ─────────────────────────────────────────────────────────────
const map = L.map('map', {
  center:          [DEFAULT_LAT, DEFAULT_LON],
  zoom:            DEFAULT_ZOOM,
  minZoom:         MIN_ZOOM,
  maxZoom:         MAX_ZOOM,
  zoomControl:     true,
  attributionControl: true,
});

// Local offline tiles. errorTileUrl keeps missing tiles from showing
// broken-image icons.
L.tileLayer('/static/tiles/{z}/{x}/{y}.png', {
  attribution:  '© OpenStreetMap contributors',
  minZoom:      MIN_ZOOM,
  maxZoom:      MAX_ZOOM,
  errorTileUrl: '/static/tiles/blank.png',
}).addTo(map);

// ── Aircraft SVG icon ────────────────────────────────────────────────────
function aircraftSVG(heading, stale) {
  const fill = stale ? '#888888' : '#3B82F6';
  // Simple aircraft silhouette — top-down view
  return `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path fill="${fill}" d="
      M12 2
      L14 8 L20 10 L20 12 L14 11 L14 16 L17 17 L17 19 L12 18 L7 19 L7 17 L10 16
      L10 11 L4 12 L4 10 L10 8 Z
    "/>
  </svg>`;
}

function makeIcon(heading, stale) {
  const angle = heading != null ? heading : 0;
  return L.divIcon({
    className: '',
    html: `
      <div class="ac-marker-icon" style="transform:rotate(${angle}deg)">
        ${aircraftSVG(heading, stale)}
      </div>`,
    iconSize:   [32, 32],
    iconAnchor: [16, 16],
    popupAnchor:[0, -20],
  });
}

// ── Popup HTML ────────────────────────────────────────────────────────────
function buildPopup(ac) {
  const alt  = ac.altitude  != null ? ac.altitude.toLocaleString() + ' ft' : '—';
  const spd  = ac.speed     != null ? Math.round(ac.speed) + ' kt' : '—';
  const hdg  = ac.heading   != null ? Math.round(ac.heading) + '°' : '—';
  const sqk  = ac.squawk || '—';
  const rssi = ac.rssi      != null ? ac.rssi.toFixed(1) + ' dBFS' : '—';
  const cs   = ac.callsign  || ac.icao;

  return `<div class="ac-popup">
    <div class="popup-callsign">${cs}</div>
    <table class="popup-table">
      <tr><td>ICAO</td><td>${ac.icao}</td></tr>
      <tr><td>Altitude</td><td>${alt}</td></tr>
      <tr><td>Speed</td><td>${spd}</td></tr>
      <tr><td>Heading</td><td>${hdg}</td></tr>
      <tr><td>Squawk</td><td>${sqk}</td></tr>
      <tr><td>RSSI</td><td>${rssi}</td></tr>
    </table>
  </div>`;
}

// ── Sidebar item ─────────────────────────────────────────────────────────
function buildSidebarItem(ac) {
  const cs  = ac.callsign || ac.icao;
  const alt = ac.altitude != null ? ac.altitude.toLocaleString() + ' ft' : '—';
  const spd = ac.speed    != null ? Math.round(ac.speed) + ' kt' : '';
  const hdg = ac.heading  != null ? Math.round(ac.heading) + '°' : '';

  const div = document.createElement('div');
  div.className = 'ac-item' + (ac.icao === selectedIcao ? ' active' : '');
  div.dataset.icao = ac.icao;
  div.innerHTML = `
    <div class="ac-icon-wrap">
      ${aircraftSVG(ac.heading, false)}
    </div>
    <div class="ac-info">
      <div class="ac-callsign">${cs}</div>
      <div class="ac-sub">${ac.icao}${spd ? '  ' + spd : ''}${hdg ? '  ' + hdg : ''}</div>
    </div>
    <div class="ac-alt">${alt}</div>`;

  div.addEventListener('click', () => {
    selectAircraft(ac.icao);
  });

  return div;
}

// ── Aircraft selection ───────────────────────────────────────────────────
function selectAircraft(icao) {
  selectedIcao = icao;
  const m = markers[icao];
  if (m) {
    map.panTo(m.marker.getLatLng());
    m.marker.openPopup();
  }
}

// ── Data update ───────────────────────────────────────────────────────────
let knownIcaos = new Set();

async function fetchAndUpdate() {
  try {
    const resp = await fetch(API_AIRCRAFT);
    if (!resp.ok) return;
    const data = await resp.json();
    const aircraft = data.aircraft || [];

    // Header badge
    const badgeCount = document.getElementById('badge-count');
    badgeCount.textContent = aircraft.length + ' AC';

    const badgeAdsb = document.getElementById('badge-adsb');
    if (data.dump1090_ok) {
      badgeAdsb.textContent = '● ADS-B OK';
      badgeAdsb.className   = 'badge ok';
    } else {
      badgeAdsb.textContent = '● ADS-B OFFLINE';
      badgeAdsb.className   = 'badge error';
    }

    // Auto-centre map on first aircraft with position
    if (!mapCentred) {
      const first = aircraft.find(a => a.lat != null && a.lon != null);
      if (first) {
        map.setView([first.lat, first.lon], DEFAULT_ZOOM);
        mapCentred = true;
      }
    }

    // Track which ICAOs are in this update
    const updatedIcaos = new Set();

    for (const ac of aircraft) {
      updatedIcaos.add(ac.icao);
      const stale = ac.seen > 30;

      if (ac.lat != null && ac.lon != null) {
        const latlng = [ac.lat, ac.lon];

        if (markers[ac.icao]) {
          // Update existing marker
          const entry = markers[ac.icao];
          entry.marker.setLatLng(latlng);
          entry.marker.setIcon(makeIcon(ac.heading, stale));
          entry.marker.setPopupContent(buildPopup(ac));
        } else {
          // Create new marker
          const marker = L.marker(latlng, { icon: makeIcon(ac.heading, stale) })
            .addTo(map)
            .bindPopup(buildPopup(ac), { maxWidth: 240 });

          marker.on('click', () => { selectedIcao = ac.icao; });
          markers[ac.icao] = { marker };
        }
      }
    }

    // Remove markers for aircraft no longer present
    for (const icao of knownIcaos) {
      if (!updatedIcaos.has(icao) && markers[icao]) {
        map.removeLayer(markers[icao].marker);
        delete markers[icao];
      }
    }
    knownIcaos = updatedIcaos;

    // Rebuild sidebar list (sorted by altitude desc)
    const sorted = [...aircraft].sort((a, b) =>
      (b.altitude || 0) - (a.altitude || 0)
    );

    const list = document.getElementById('ac-list');
    const countLbl = document.getElementById('ac-count-label');
    countLbl.textContent = aircraft.length;

    if (aircraft.length === 0) {
      list.innerHTML = '<div class="ac-empty">No aircraft detected</div>';
    } else {
      list.innerHTML = '';
      for (const ac of sorted) {
        list.appendChild(buildSidebarItem(ac));
      }
    }

  } catch (e) {
    console.warn('Fetch error:', e);
  }
}

async function fetchSystem() {
  try {
    const [statsResp, sysResp] = await Promise.all([
      fetch(API_STATS),
      fetch(API_SYSTEM),
    ]);
    const stats = await statsResp.json();
    const sys   = await sysResp.json();

    const el = id => document.getElementById(id);
    el('s-rate').textContent = (stats.messages_rate || 0).toFixed(1);
    el('s-temp').textContent = sys.cpu_temp_c != null ? sys.cpu_temp_c.toFixed(1) + ' °C' : '—';
    el('s-ram').textContent  = sys.ram_percent != null ? sys.ram_percent.toFixed(0) + ' %' : '—';
  } catch (e) { /* ignore */ }
}

// ── Clock ─────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2,'0');
  const mm = String(now.getMinutes()).padStart(2,'0');
  const ss = String(now.getSeconds()).padStart(2,'0');
  document.getElementById('clock').textContent = `${hh}:${mm}:${ss}`;
}

// ── Boot ──────────────────────────────────────────────────────────────────
updateClock();
setInterval(updateClock, 1000);

fetchAndUpdate();
fetchSystem();
setInterval(fetchAndUpdate, REFRESH_MS);
setInterval(fetchSystem, 5000);
