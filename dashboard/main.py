#!/usr/bin/env python3
"""
ADS-B Dashboard - Main Application Entry Point
Kivy-based touchscreen dashboard for Raspberry Pi 3
"""

import os
import sys

# Must be set before Kivy imports
os.environ['KIVY_NO_ENV_CONFIG'] = '1'
os.environ['KIVY_NO_CONSOLELOG'] = '1'

# Force OpenGL ES2 for RPi GPU
os.environ['KIVY_GL_BACKEND'] = 'sdl2'

import kivy
kivy.require('2.1.0')

from kivy.config import Config

# Touchscreen / display settings
Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '480')
Config.set('graphics', 'fullscreen', 'auto')
Config.set('graphics', 'show_cursor', '0')
Config.set('graphics', 'borderless', '1')
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
Config.set('kivy', 'log_level', 'warning')
Config.set('kivy', 'exit_on_escape', '0')

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.core.window import Window
from kivy.clock import Clock

from screens.home import HomeScreen
from screens.map import MapScreen
from screens.settings import SettingsScreen
from utils.theme import Theme

Window.clearcolor = Theme.BG


class ADSBDashboardApp(App):
    """Root application class."""

    def build(self):
        self.title = 'ADS-B Dashboard'
        self.icon = ''

        # Hide cursor for touchscreen-only operation
        Window.show_cursor = False

        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(MapScreen(name='map'))
        sm.add_widget(SettingsScreen(name='settings'))

        return sm

    def on_start(self):
        # Prevent screen from sleeping
        try:
            import subprocess
            subprocess.run(['xset', 's', 'off'], capture_output=True)
            subprocess.run(['xset', '-dpms'], capture_output=True)
            subprocess.run(['xset', 's', 'noblank'], capture_output=True)
        except Exception:
            pass


if __name__ == '__main__':
    ADSBDashboardApp().run()
