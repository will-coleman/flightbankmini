"""
Home Screen — main ADS-B dashboard.
Card layout: System Info | WiFi Control | Map | Settings
"""

import threading
from datetime import datetime

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle, Line

from utils.theme import Theme
from utils.sysmetrics import get_metrics
from utils.adsb_client import fetch_stats
from utils import hotspot
from widgets.cards import (
    Card, MetricRow, DividerLine, PrimaryButton,
    ToggleCard, StatusBadge
)


class HeaderBar(BoxLayout):
    """Full-width dark header: device name | time | ADS-B status | WiFi status."""

    def __init__(self, **kwargs):
        kwargs['orientation']  = 'horizontal'
        kwargs['size_hint_y']  = None
        kwargs['height']       = dp(Theme.HEADER_HEIGHT)
        kwargs['padding']      = [dp(Theme.PAD_MD), 0, dp(Theme.PAD_MD), 0]
        kwargs['spacing']      = dp(Theme.PAD_SM)
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*Theme.HEADER_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update, size=self._update)

        # Device name
        self._name = Label(
            text='ADS-B RADAR',
            font_size=sp(Theme.FONT_LG),
            bold=True,
            color=Theme.HEADER_TEXT,
            size_hint_x=None,
            width=dp(160),
            halign='left',
            valign='middle',
        )
        self._name.bind(size=self._name.setter('text_size'))
        self.add_widget(self._name)

        # Spacer
        self.add_widget(Widget())

        # Current time
        self._clock_lbl = Label(
            text='00:00:00',
            font_size=sp(Theme.FONT_LG),
            bold=True,
            color=Theme.HEADER_TEXT,
            size_hint_x=None,
            width=dp(100),
            halign='center',
            valign='middle',
        )
        self._clock_lbl.bind(size=self._clock_lbl.setter('text_size'))
        self.add_widget(self._clock_lbl)

        # Spacer
        self.add_widget(Widget())

        # ADS-B status badge
        self._adsb_badge = StatusBadge(Theme.WARNING, 'ADS-B INIT')
        self.add_widget(self._adsb_badge)

        # WiFi badge
        self._wifi_badge = StatusBadge(Theme.TEXT_MUTED, 'HOTSPOT OFF')
        self.add_widget(self._wifi_badge)

    def _update(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def tick(self):
        now = datetime.now()
        self._clock_lbl.text = now.strftime('%H:%M:%S')

    def set_adsb_status(self, ok: bool, aircraft: int = 0):
        if ok:
            self._adsb_badge.update(f'ADS-B  {aircraft}AC', Theme.SUCCESS)
        else:
            self._adsb_badge.update('ADS-B OFFLINE', Theme.DANGER)

    def set_wifi_status(self, active: bool):
        if active:
            self._wifi_badge.update('HOTSPOT ON', Theme.SUCCESS)
        else:
            self._wifi_badge.update('HOTSPOT OFF', Theme.TEXT_MUTED)


class SystemInfoCard(Card):
    """Left card: live system metrics."""

    def __init__(self, **kwargs):
        super().__init__(title='System', **kwargs)

        self._rows = {}
        metrics = [
            ('cpu_temp',   'CPU Temp',       '—'),
            ('cpu_usage',  'CPU Usage',      '—'),
            ('ram',        'RAM',            '—'),
            ('disk',       'Storage',        '—'),
            ('uptime',     'Uptime',         '—'),
        ]
        for key, label, default in metrics:
            row = MetricRow(label=label, value=default)
            self._rows[key] = row
            self.add_widget(row)

        self.add_widget(DividerLine())

        self._rows['adsb_rate']    = MetricRow(label='Msg/sec',  value='—')
        self._rows['adsb_tracked'] = MetricRow(label='Tracked',  value='—')
        self.add_widget(self._rows['adsb_rate'])
        self.add_widget(self._rows['adsb_tracked'])

        # Push rows to top
        self.add_widget(Widget())

    def update(self, metrics, adsb_stats):
        self._rows['cpu_temp'].set_value(f"{metrics.cpu_temp:.1f} °C")
        self._rows['cpu_usage'].set_value(f"{metrics.cpu_usage:.1f} %")
        self._rows['ram'].set_value(
            f"{metrics.ram_used_mb:.0f} / {metrics.ram_total_mb:.0f} MB"
        )
        self._rows['disk'].set_value(
            f"{metrics.disk_used_gb:.1f} / {metrics.disk_total_gb:.1f} GB"
        )
        self._rows['uptime'].set_value(metrics.uptime_str)
        self._rows['adsb_rate'].set_value(f"{adsb_stats.messages_rate:.1f}")
        self._rows['adsb_tracked'].set_value(str(adsb_stats.aircraft_total))


class WiFiCard(Card):
    """Right top card: hotspot toggle."""

    def __init__(self, on_status_change=None, **kwargs):
        super().__init__(title='WiFi Hotspot', **kwargs)
        self._on_status_change = on_status_change
        self._active = hotspot.is_hotspot_active()
        self._pending = False

        cfg = hotspot.load_config()

        # SSID / password info row
        self._ssid_row = MetricRow(label='SSID', value=cfg['ssid'])
        self.add_widget(self._ssid_row)

        self._ip_row = MetricRow(label='IP', value=cfg['ip'])
        self.add_widget(self._ip_row)

        self.add_widget(DividerLine())

        # Status text
        self._status_lbl = Label(
            text='',
            font_size=sp(Theme.FONT_MD),
            size_hint_y=None,
            height=dp(28),
            halign='left',
            valign='middle',
            color=Theme.TEXT_MUTED,
        )
        self._status_lbl.bind(size=self._status_lbl.setter('text_size'))
        self.add_widget(self._status_lbl)

        # Toggle button
        self._btn = PrimaryButton(
            text='ENABLE HOTSPOT',
            on_press_cb=self._toggle,
        )
        self.add_widget(self._btn)

        self.add_widget(Widget())
        self._refresh_ui()

    def _refresh_ui(self):
        if self._active:
            self._btn.text = 'DISABLE HOTSPOT'
            self._btn._btn_color.rgba = Theme.DANGER
            self._status_lbl.text  = 'Hotspot Active — 192.168.4.1'
            self._status_lbl.color = Theme.SUCCESS
        else:
            self._btn.text = 'ENABLE HOTSPOT'
            self._btn._btn_color.rgba = Theme.ACCENT
            self._status_lbl.text  = 'Hotspot Disabled'
            self._status_lbl.color = Theme.TEXT_MUTED

    def _toggle(self):
        if self._pending:
            return
        self._pending = True
        self._btn.text = 'PLEASE WAIT...'

        def _work():
            cfg = hotspot.load_config()
            if self._active:
                ok, msg = hotspot.stop_hotspot()
                new_state = not ok
            else:
                ok, msg = hotspot.start_hotspot(cfg['ssid'], cfg['password'])
                new_state = ok

            def _done(dt):
                self._active  = new_state
                self._pending = False
                self._refresh_ui()
                if self._on_status_change:
                    self._on_status_change(new_state)

            Clock.schedule_once(_done, 0)

        threading.Thread(target=_work, daemon=True).start()


class MapCard(Card):
    """Card with OPEN MAP button."""

    def __init__(self, on_open_map=None, **kwargs):
        super().__init__(title='ADS-B Map', **kwargs)

        self._tracked_lbl = Label(
            text='Aircraft: —',
            font_size=sp(Theme.FONT_2XL),
            bold=True,
            color=Theme.TEXT,
            size_hint_y=None,
            height=dp(48),
            halign='center',
            valign='middle',
        )
        self._tracked_lbl.bind(size=self._tracked_lbl.setter('text_size'))
        self.add_widget(self._tracked_lbl)

        self._pos_lbl = Label(
            text='With position: —',
            font_size=sp(Theme.FONT_MD),
            color=Theme.TEXT_MUTED,
            size_hint_y=None,
            height=dp(24),
            halign='center',
            valign='middle',
        )
        self._pos_lbl.bind(size=self._pos_lbl.setter('text_size'))
        self.add_widget(self._pos_lbl)

        self.add_widget(Widget())

        self._open_btn = PrimaryButton(
            text='OPEN MAP',
            on_press_cb=on_open_map or (lambda: None),
        )
        self.add_widget(self._open_btn)

    def update(self, adsb_stats):
        self._tracked_lbl.text = f"Aircraft: {adsb_stats.aircraft_total}"
        self._pos_lbl.text = f"With position: {adsb_stats.aircraft_with_pos}"


class SettingsCard(Card):
    """Placeholder settings card."""

    def __init__(self, **kwargs):
        super().__init__(title='Settings', **kwargs)

        self.add_widget(Widget())

        placeholder = Label(
            text='Future expansion',
            font_size=sp(Theme.FONT_MD),
            color=Theme.TEXT_MUTED,
            halign='center',
            valign='middle',
        )
        placeholder.bind(size=placeholder.setter('text_size'))
        self.add_widget(placeholder)

        self.add_widget(Widget())


class HomeScreen(Screen):
    """
    Main dashboard screen.
    Layout: Header | 2×2 card grid
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation='vertical', spacing=0)

        # ── Header ──────────────────────────────────────────────
        self._header = HeaderBar()
        root.add_widget(self._header)

        # ── Card grid ───────────────────────────────────────────
        grid = GridLayout(
            cols=2,
            spacing=dp(2),
            padding=[dp(2), dp(2), dp(2), dp(2)],
        )

        pad = [dp(Theme.PAD_LG)] * 4

        self._sys_card  = SystemInfoCard(padding=pad)
        self._wifi_card = WiFiCard(
            on_status_change=self._on_wifi_change,
            padding=pad,
        )
        self._map_card  = MapCard(
            on_open_map=self._go_to_map,
            padding=pad,
        )
        self._set_card  = SettingsCard(padding=pad)

        grid.add_widget(self._sys_card)
        grid.add_widget(self._wifi_card)
        grid.add_widget(self._map_card)
        grid.add_widget(self._set_card)

        root.add_widget(grid)
        self.add_widget(root)

        # ── Background fill ─────────────────────────────────────
        with self.canvas.before:
            Color(*Theme.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # ── Data state ──────────────────────────────────────────
        self._adsb_stats = None

    def _update_bg(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size

    def on_enter(self):
        Clock.schedule_interval(self._tick, 1.0)

    def on_leave(self):
        Clock.unschedule(self._tick)

    def _tick(self, dt):
        self._header.tick()

        def _fetch():
            metrics = get_metrics()
            stats   = fetch_stats()
            def _update(dt):
                self._adsb_stats = stats
                self._sys_card.update(metrics, stats)
                self._map_card.update(stats)
                self._header.set_adsb_status(
                    stats.aircraft_total > 0 or stats.messages_rate > 0,
                    stats.aircraft_total,
                )
            Clock.schedule_once(_update, 0)

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_wifi_change(self, active: bool):
        self._header.set_wifi_status(active)

    def _go_to_map(self):
        self.manager.current = 'map'
