"""Settings screen — placeholder for future expansion."""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle

from utils.theme import Theme
from widgets.cards import PrimaryButton


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(*Theme.BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, 'pos', self.pos),
                  size=lambda *_: setattr(self._bg, 'size', self.size))

        root = BoxLayout(orientation='vertical', padding=[dp(24)] * 4, spacing=dp(16))

        back = PrimaryButton(
            text='◀  BACK',
            on_press_cb=lambda: setattr(self.manager, 'current', 'home'),
            size_hint_x=None, width=dp(140),
        )

        topbar = BoxLayout(size_hint_y=None, height=dp(56))
        topbar.add_widget(back)
        topbar.add_widget(Widget())
        root.add_widget(topbar)

        lbl = Label(
            text='Settings\n\nFuture expansion area.',
            font_size=sp(Theme.FONT_LG),
            color=Theme.TEXT_MUTED,
            halign='center', valign='middle',
        )
        lbl.bind(size=lbl.setter('text_size'))
        root.add_widget(lbl)
        self.add_widget(root)
