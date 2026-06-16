"""
Reusable card and button widgets for the ADS-B dashboard.
Industrial, aviation-appliance aesthetic.
"""

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, Rectangle, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import (
    StringProperty, ColorProperty, BooleanProperty, NumericProperty
)

from utils.theme import Theme


class Card(BoxLayout):
    """
    Base card widget.
    White (#F5F5F5) fill, #C8C8C8 border, subtle 4dp radius.
    """

    title = StringProperty('')

    def __init__(self, title='', padding_inner=None, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('padding', [dp(Theme.PAD_MD)] * 4)
        kwargs.setdefault('spacing', dp(Theme.PAD_SM))
        super().__init__(**kwargs)

        self.title = title

        with self.canvas.before:
            # Card fill
            Color(*Theme.CARD)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            # Card border
            Color(*Theme.BORDER)
            self._border_rect = Line(rectangle=[self.x, self.y, self.width, self.height], width=1)

        self.bind(pos=self._update_bg, size=self._update_bg)

        if title:
            header = CardHeader(title=title)
            self.add_widget(header)

    def _update_bg(self, *_):
        self._bg_rect.pos  = self.pos
        self._bg_rect.size = self.size
        self._border_rect.rectangle = [self.x, self.y, self.width, self.height]


class CardHeader(BoxLayout):
    """Top label row inside a card."""

    title = StringProperty('')

    def __init__(self, title='', **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(32))
        super().__init__(**kwargs)
        self.title = title
        self._build()

    def _build(self):
        self.clear_widgets()
        lbl = Label(
            text=self.title.upper(),
            font_size=sp(Theme.FONT_SM),
            color=Theme.TEXT_MUTED,
            bold=True,
            halign='left',
            valign='middle',
            size_hint_x=1,
        )
        lbl.bind(size=lbl.setter('text_size'))
        self.add_widget(lbl)

    def on_title(self, *_):
        self._build()


class MetricRow(BoxLayout):
    """
    Single labelled metric row: [LABEL]  [VALUE]
    Used inside System Information card.
    """

    def __init__(self, label: str, value: str = '—', **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(28))
        super().__init__(**kwargs)

        self._label_widget = Label(
            text=label,
            font_size=sp(Theme.FONT_MD),
            color=Theme.TEXT_MUTED,
            halign='left',
            valign='middle',
            size_hint_x=0.55,
        )
        self._label_widget.bind(size=self._label_widget.setter('text_size'))

        self._value_widget = Label(
            text=value,
            font_size=sp(Theme.FONT_MD),
            color=Theme.TEXT,
            bold=True,
            halign='right',
            valign='middle',
            size_hint_x=0.45,
        )
        self._value_widget.bind(size=self._value_widget.setter('text_size'))

        self.add_widget(self._label_widget)
        self.add_widget(self._value_widget)

    def set_value(self, value: str):
        self._value_widget.text = value

    def set_label(self, label: str):
        self._label_widget.text = label


class DividerLine(Widget):
    """Thin 1px horizontal divider in BORDER colour."""

    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(1))
        super().__init__(**kwargs)
        with self.canvas:
            Color(*Theme.BORDER)
            self._line = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._line.pos  = self.pos
        self._line.size = self.size


class PrimaryButton(ButtonBehavior, BoxLayout):
    """
    Large, flat touch button — accent blue fill, white text.
    Min height 56dp for fat-finger usability.
    """

    text     = StringProperty('Button')
    disabled = BooleanProperty(False)

    def __init__(self, text='Button', on_press_cb=None, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(Theme.BTN_HEIGHT))
        super().__init__(**kwargs)

        self.text = text
        self._cb  = on_press_cb

        with self.canvas.before:
            self._btn_color = Color(*Theme.ACCENT)
            self._btn_rect  = Rectangle(pos=self.pos, size=self.size)
            Color(*Theme.ACCENT_DARK)
            self._border    = Line(rectangle=[self.x, self.y, self.width, self.height], width=1.2)

        self._lbl = Label(
            text=self.text,
            font_size=sp(Theme.FONT_LG),
            bold=True,
            color=Theme.WHITE,
        )
        self.add_widget(self._lbl)

        self.bind(pos=self._update_bg, size=self._update_bg)
        self.bind(text=lambda *_: setattr(self._lbl, 'text', self.text))

    def _update_bg(self, *_):
        self._btn_rect.pos  = self.pos
        self._btn_rect.size = self.size
        self._border.rectangle = [self.x, self.y, self.width, self.height]

    def on_press(self):
        if not self.disabled and self._cb:
            self._cb()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._btn_color.rgba = Theme.ACCENT_DARK
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        self._btn_color.rgba = Theme.ACCENT
        return super().on_touch_up(touch)


class ToggleCard(Card):
    """
    Card with a large ON/OFF toggle button.
    State managed externally via set_state().
    """

    def __init__(self, title='', on_toggle=None, **kwargs):
        super().__init__(title=title, **kwargs)
        self._on_toggle = on_toggle
        self._state = False

        self._status_label = Label(
            text='Disabled',
            font_size=sp(Theme.FONT_MD),
            color=Theme.TEXT_MUTED,
            size_hint_y=None,
            height=dp(24),
            halign='left',
            valign='middle',
        )
        self._status_label.bind(size=self._status_label.setter('text_size'))
        self.add_widget(self._status_label)

        self._toggle_btn = PrimaryButton(
            text='ENABLE',
            on_press_cb=self._handle_toggle,
        )
        self.add_widget(self._toggle_btn)

    def set_state(self, active: bool, status_text: str = ''):
        self._state = active
        if active:
            self._toggle_btn.text = 'DISABLE'
            self._toggle_btn._btn_color.rgba = Theme.DANGER
            self._status_label.text = status_text or 'Active'
            self._status_label.color = Theme.SUCCESS
        else:
            self._toggle_btn.text = 'ENABLE'
            self._toggle_btn._btn_color.rgba = Theme.ACCENT
            self._status_label.text = status_text or 'Disabled'
            self._status_label.color = Theme.TEXT_MUTED

    def _handle_toggle(self):
        if self._on_toggle:
            self._on_toggle(not self._state)


class StatusBadge(BoxLayout):
    """
    Small coloured status pill for header bar.
    e.g. '● ADS-B OK'
    """

    def __init__(self, dot_color, label: str, **kwargs):
        kwargs.setdefault('size_hint_x', None)
        kwargs.setdefault('width', dp(120))
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(Theme.HEADER_HEIGHT))
        super().__init__(**kwargs)

        self._dot_color = dot_color
        self._lbl_text  = label

        self._lbl = Label(
            text=f'● {label}',
            font_size=sp(Theme.FONT_SM),
            color=dot_color,
            halign='center',
            valign='middle',
        )
        self._lbl.bind(size=self._lbl.setter('text_size'))
        self.add_widget(self._lbl)

    def update(self, label: str, color=None):
        self._lbl_text = label
        if color:
            self._dot_color = color
        self._lbl.text  = f'● {label}'
        self._lbl.color = self._dot_color
