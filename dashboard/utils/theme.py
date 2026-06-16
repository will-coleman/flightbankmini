"""
ADS-B Dashboard Theme
Centralised colour/typography constants — industrial aviation palette.
"""

from kivy.utils import get_color_from_hex


def hex_color(h: str):
    """Convert hex string to Kivy RGBA tuple."""
    return get_color_from_hex(h)


class Theme:
    # ── Base palette ──────────────────────────────────────────────
    BG          = hex_color('#DDDDDD')
    CARD        = hex_color('#F5F5F5')
    BORDER      = hex_color('#C8C8C8')
    TEXT        = hex_color('#222222')
    TEXT_MUTED  = hex_color('#666666')
    ACCENT      = hex_color('#3B82F6')
    ACCENT_DARK = hex_color('#1D4ED8')
    SUCCESS     = hex_color('#16A34A')
    WARNING     = hex_color('#D97706')
    DANGER      = hex_color('#DC2626')
    WHITE       = hex_color('#FFFFFF')
    BLACK       = hex_color('#000000')

    # Header specific
    HEADER_BG   = hex_color('#222222')
    HEADER_TEXT = hex_color('#F5F5F5')

    # ── Typography (sizes in sp) ───────────────────────────────────
    FONT_XS   = 10
    FONT_SM   = 12
    FONT_MD   = 14
    FONT_LG   = 16
    FONT_XL   = 20
    FONT_2XL  = 24
    FONT_3XL  = 32

    # ── Spacing (dp) ──────────────────────────────────────────────
    PAD_XS = 4
    PAD_SM = 8
    PAD_MD = 12
    PAD_LG = 16
    PAD_XL = 24

    # ── Radii ─────────────────────────────────────────────────────
    RADIUS = 4          # Subtle, industrial — never more than 8px

    # ── Touch targets ─────────────────────────────────────────────
    TOUCH_MIN = 48      # Minimum finger target height (dp)
    BTN_HEIGHT = 56
    HEADER_HEIGHT = 52
