"""
Map Screen — native in-dashboard ADS-B map.

Renders directly inside Kivy using kivy_garden.mapview (no Chromium).
Loads the offline tiles served locally by the backend and overlays live
aircraft as markers. BACK returns to the home screen.
"""

import math
import json
import threading
import urllib.request

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.clock import Clock, mainthread
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.graphics import Color, Rectangle, Ellipse, Line

from kivy_garden.mapview import MapView, MapSource, MapMarker

from utils.theme import Theme
from widgets.cards import PrimaryButton

# ── Config ────────────────────────────────────────────────────────────────
API_AIRCRAFT = 'http://127.0.0.1:5000/api/aircraft'
# Offline tiles served locally by Flask (/static/tiles). No internet needed.
TILE_URL = 'http://127.0.0.1:5000/static/tiles/{z}/{x}/{y}.png'

DEFAULT_LAT  = 51.477
DEFAULT_LON  = -0.461
DEFAULT_ZOOM = 8
MIN_ZOOM     = 6
MAX_ZOOM     = 11
REFRESH_S    = 2.0


class AircraftMarker(MapMarker):
    """Blue dot with a white heading line. No external image needed."""
    heading = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.source = ''
        self.size_hint = (None, None)
        self.size = (dp(16), dp(16))
        self.anchor_x = 0.5
        self.anchor_y = 0.5
        self.bind(pos=self._redraw, size=self._redraw, heading=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.after.clear()
        cx = self.x + self.width / 2.0
        cy = self.y + self.height / 2.0
        r  = self.width / 2.0
        with self.canvas.after:
            Color(0.23, 0.51, 0.96, 1)
            Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            Color(1, 1, 1, 1)
            ang = math.radians(90 - self.heading)   # 0° heading = North = up
            ex = cx + r * 1.8 * math.cos(ang)
            ey = cy + r * 1.8 * math.sin(ang)
            Line(points=[cx, cy, ex, ey], width=dp(1.4))


class MapScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._markers = {}        # icao -> AircraftMarker
        self._poll_ev = None
        self._centred = False

        with self.canvas.before:
            Color(*Theme.HEADER_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        root = BoxLayout(orientation='vertical')

        # ── Top bar with working BACK button ──────────────────
        topbar = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(Theme.HEADER_HEIGHT),
            padding=[dp(8), dp(4), dp(8), dp(4)],
            spacing=dp(8),
        )
        with topbar.canvas.before:
            Color(*Theme.HEADER_BG)
            self._bar_bg = Rectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=self._upd_bar, size=self._upd_bar)
        self._topbar = topbar

        back_btn = PrimaryButton(
            text='◀  BACK',
            on_press_cb=self._go_back,
            size_hint_x=None,
            width=dp(120),
        )
        topbar.add_widget(back_btn)

        self._title = Label(
            text='ADS-B MAP',
            font_size=sp(Theme.FONT_LG),
            bold=True,
            color=Theme.HEADER_TEXT,
            halign='left',
            valign='middle',
        )
        self._title.bind(size=self._title.setter('text_size'))
        topbar.add_widget(self._title)

        self._count = Label(
            text='0 AC',
            font_size=sp(Theme.FONT_MD),
            color=Theme.HEADER_TEXT,
            size_hint_x=None,
            width=dp(80),
            halign='right',
            valign='middle',
        )
        self._count.bind(size=self._count.setter('text_size'))
        topbar.add_widget(self._count)

        root.add_widget(topbar)

        # ── The map itself ────────────────────────────────────
        source = MapSource(
            url=TILE_URL,
            cache_key='fbradar_offline',
            min_zoom=MIN_ZOOM,
            max_zoom=MAX_ZOOM,
            attribution='Geoapify | © OpenStreetMap',
        )
        self.mapview = MapView(
            map_source=source,
            zoom=DEFAULT_ZOOM,
            lat=DEFAULT_LAT,
            lon=DEFAULT_LON,
        )
        root.add_widget(self.mapview)

        self.add_widget(root)

    # ── Canvas helpers ────────────────────────────────────────
    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _upd_bar(self, *_):
        self._bar_bg.pos = self._topbar.pos
        self._bar_bg.size = self._topbar.size

    # ── Screen lifecycle ──────────────────────────────────────
    def on_enter(self):
        self._poll_ev = Clock.schedule_interval(self._tick, REFRESH_S)
        self._tick(0)

    def on_leave(self):
        if self._poll_ev:
            self._poll_ev.cancel()
            self._poll_ev = None

    def _go_back(self):
        self.manager.current = 'home'

    # ── Data polling (network off the UI thread) ──────────────
    def _tick(self, _dt):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            with urllib.request.urlopen(API_AIRCRAFT, timeout=3) as r:
                data = json.loads(r.read())
        except Exception:
            return
        self._apply(data.get('aircraft', []))

    @mainthread
    def _apply(self, aircraft):
        positioned = [a for a in aircraft
                      if a.get('lat') is not None and a.get('lon') is not None]
        self._count.text = f'{len(aircraft)} AC'

        # Centre once on the first aircraft we see with a position
        if not self._centred and positioned:
            a = positioned[0]
            self.mapview.center_on(a['lat'], a['lon'])
            self._centred = True

        seen = set()
        for a in positioned:
            icao = a['icao']
            seen.add(icao)
            hdg = a.get('heading') or 0
            m = self._markers.get(icao)
            if m is None:
                m = AircraftMarker(lat=a['lat'], lon=a['lon'], heading=hdg)
                self._markers[icao] = m
                self.mapview.add_marker(m)
            else:
                # Reposition by removing and re-adding (mapview has no in-place move)
                self.mapview.remove_marker(m)
                m.lat = a['lat']
                m.lon = a['lon']
                m.heading = hdg
                self.mapview.add_marker(m)

        # Drop aircraft that have gone
        for icao in list(self._markers.keys()):
            if icao not in seen:
                self.mapview.remove_marker(self._markers[icao])
                del self._markers[icao]
