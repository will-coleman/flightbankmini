"""
Map Screen — lightweight "view on your phone" panel.

Designed for the Pi 3 Model A+ (512MB RAM): no Chromium, no in-Kivy map
widget — both are too heavy for 512MB. The full Leaflet map is viewed on
any phone/laptop connected to the ADSB-RADAR hotspot. This screen just
shows the URL and a live aircraft count, with a working BACK button.
"""

import json
import threading
import urllib.request

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.clock import Clock, mainthread
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle

from utils.theme import Theme
from widgets.cards import PrimaryButton

API_AIRCRAFT = 'http://127.0.0.1:5000/api/aircraft'
HOTSPOT_URL  = 'http://192.168.4.1'
REFRESH_S    = 3.0


class MapScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._poll_ev = None

        with self.canvas.before:
            Color(*Theme.HEADER_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        root = BoxLayout(orientation='vertical')

        # ── Top bar with BACK button ──────────────────────────
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
        topbar.add_widget(Widget())

        root.add_widget(topbar)

        # ── Centre content ────────────────────────────────────
        body = BoxLayout(
            orientation='vertical',
            padding=[dp(24)] * 4,
            spacing=dp(12),
        )
        body.add_widget(Widget())

        headline = Label(
            text='View the live map on your phone',
            font_size=sp(Theme.FONT_LG),
            bold=True,
            color=Theme.HEADER_TEXT,
            halign='center',
            valign='middle',
        )
        headline.bind(size=headline.setter('text_size'))
        body.add_widget(headline)

        url_lbl = Label(
            text='[b]' + HOTSPOT_URL + '[/b]',
            font_size=sp(Theme.FONT_LG + 6),
            color=Theme.ACCENT if hasattr(Theme, 'ACCENT') else Theme.HEADER_TEXT,
            markup=True,
            halign='center',
            valign='middle',
        )
        url_lbl.bind(size=url_lbl.setter('text_size'))
        body.add_widget(url_lbl)

        steps = Label(
            text=('1.  Connect to Wi-Fi  [b]ADSB-RADAR[/b]\n'
                  '2.  Open  [b]' + HOTSPOT_URL + '[/b]  in any browser'),
            font_size=sp(Theme.FONT_MD),
            color=Theme.HEADER_TEXT,
            markup=True,
            halign='center',
            valign='middle',
        )
        steps.bind(size=steps.setter('text_size'))
        body.add_widget(steps)

        self._count = Label(
            text='Tracking 0 aircraft',
            font_size=sp(Theme.FONT_MD),
            color=Theme.HEADER_TEXT,
            halign='center',
            valign='middle',
        )
        self._count.bind(size=self._count.setter('text_size'))
        body.add_widget(self._count)

        body.add_widget(Widget())
        root.add_widget(body)

        self.add_widget(root)

    # ── Canvas helpers ────────────────────────────────────────
    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _upd_bar(self, *_):
        self._bar_bg.pos = self._topbar.pos
        self._bar_bg.size = self._topbar.size

    # ── Lifecycle ─────────────────────────────────────────────
    def on_enter(self):
        self._poll_ev = Clock.schedule_interval(self._tick, REFRESH_S)
        self._tick(0)

    def on_leave(self):
        if self._poll_ev:
            self._poll_ev.cancel()
            self._poll_ev = None

    def _go_back(self):
        self.manager.current = 'home'

    # ── Lightweight count poll ────────────────────────────────
    def _tick(self, _dt):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            with urllib.request.urlopen(API_AIRCRAFT, timeout=3) as r:
                data = json.loads(r.read())
        except Exception:
            return
        self._show(data.get('total', 0), data.get('with_pos', 0))

    @mainthread
    def _show(self, total, with_pos):
        self._count.text = f'Tracking {total} aircraft  ({with_pos} with position)'
