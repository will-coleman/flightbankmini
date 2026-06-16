"""
Map Screen — fullscreen ADS-B aircraft map.
Uses a Kivy WebView (via cefpython3 or system browser subprocess).
On Pi, opens Chromium kiosk pointing at the local web interface.
"""

import subprocess
import os

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle

from utils.theme import Theme
from widgets.cards import PrimaryButton


MAP_URL = 'http://127.0.0.1:5000/'
_browser_proc = None


class MapScreen(Screen):
    """
    Opens Chromium in kiosk mode as a subprocess covering the display.
    Returns to dashboard on BACK press (kills browser).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*Theme.HEADER_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        root = BoxLayout(orientation='vertical')

        # ── Thin top bar with BACK button ─────────────────────
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

        # ── Message area (browser launched externally) ─────────
        msg_box = BoxLayout(
            orientation='vertical',
            padding=[dp(24)] * 4,
            spacing=dp(16),
        )

        self._msg = Label(
            text='Opening map in browser...\n\nURL: http://127.0.0.1:5000',
            font_size=sp(Theme.FONT_LG),
            color=Theme.HEADER_TEXT,
            halign='center',
            valign='middle',
            markup=True,
        )
        self._msg.bind(size=self._msg.setter('text_size'))
        msg_box.add_widget(self._msg)

        root.add_widget(msg_box)
        self.add_widget(root)

    def _upd(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def _upd_bar(self, *_):
        self._bar_bg.pos  = self._topbar.pos
        self._bar_bg.size = self._topbar.size

    def on_enter(self):
        Clock.schedule_once(self._launch_browser, 0.3)

    def on_leave(self):
        self._kill_browser()

    def _launch_browser(self, dt):
        global _browser_proc
        self._kill_browser()
        try:
            env = os.environ.copy()
            env['DISPLAY'] = ':0'
            _browser_proc = subprocess.Popen([
                'chromium-browser',
                '--kiosk',
                '--noerrdialogs',
                '--disable-infobars',
                '--no-first-run',
                '--disable-session-crashed-bubble',
                '--disable-restore-session-state',
                '--app=' + MAP_URL,
            ], env=env)
            self._msg.text = (
                f'Map open at:\n[b]{MAP_URL}[/b]\n\n'
                'Also accessible from any device\non the ADSB-RADAR hotspot.'
            )
        except FileNotFoundError:
            self._msg.text = (
                'Chromium not found.\n\n'
                f'Open a browser and navigate to:\n[b]{MAP_URL}[/b]'
            )

    def _kill_browser(self):
        global _browser_proc
        if _browser_proc and _browser_proc.poll() is None:
            _browser_proc.terminate()
            _browser_proc = None

    def _go_back(self):
        self._kill_browser()
        self.manager.current = 'home'
