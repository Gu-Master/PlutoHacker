from typing import Dict, Optional

from PyQt6.QtGui import QColor, QPalette

from urh import settings

DEFAULT_THEME_INDEX = 2

ACCENT_COLOR = QColor(230, 168, 72)
ACCENT_SECONDARY_COLOR = QColor(96, 165, 250)
SUCCESS_COLOR = QColor(74, 222, 128)
WARNING_COLOR = QColor(245, 158, 11)
ERROR_COLOR = QColor(248, 113, 113)
INFO_COLOR = QColor(56, 189, 248)
SURFACE_BORDER_COLOR = QColor(73, 85, 110)

_LIGHT_THEME = {
    "window": QColor(245, 241, 234),
    "window_text": QColor(34, 43, 62),
    "base": QColor(255, 252, 247),
    "alternate_base": QColor(235, 229, 219),
    "button": QColor(232, 224, 211),
    "button_text": QColor(34, 43, 62),
    "tooltip_base": QColor(255, 252, 247),
    "tooltip_text": QColor(34, 43, 62),
    "text": QColor(34, 43, 62),
    "placeholder": QColor(104, 118, 143),
    "highlight": QColor(203, 126, 40),
    "highlighted_text": QColor(255, 250, 243),
    "link": QColor(56, 104, 196),
    "link_visited": QColor(101, 84, 180),
    "mid": QColor(187, 177, 160),
    "dark": QColor(142, 131, 115),
    "shadow": QColor(106, 97, 83),
    "bright_text": QColor(255, 250, 243),
    "disabled_text": QColor(151, 142, 126),
}

_DARK_THEME = {
    "window": QColor(18, 24, 38),
    "window_text": QColor(231, 237, 245),
    "base": QColor(22, 31, 48),
    "alternate_base": QColor(28, 39, 61),
    "button": QColor(31, 41, 61),
    "button_text": QColor(231, 237, 245),
    "tooltip_base": QColor(32, 43, 67),
    "tooltip_text": QColor(243, 244, 246),
    "text": QColor(231, 237, 245),
    "placeholder": QColor(148, 163, 184),
    "highlight": QColor(230, 168, 72),
    "highlighted_text": QColor(16, 22, 34),
    "link": QColor(125, 211, 252),
    "link_visited": QColor(196, 181, 253),
    "mid": QColor(73, 85, 110),
    "dark": QColor(49, 60, 81),
    "shadow": QColor(15, 23, 42),
    "bright_text": QColor(255, 251, 235),
    "disabled_text": QColor(107, 118, 138),
}


def _theme_colors(theme_index: int) -> Optional[Dict[str, QColor]]:
    if theme_index == 1:
        return _LIGHT_THEME
    if theme_index == 2:
        return _DARK_THEME
    return None


def read_theme_index(default: int = DEFAULT_THEME_INDEX) -> int:
    return settings.read("theme_index", default, int)


def build_application_palette(theme_index: int) -> Optional[QPalette]:
    colors = _theme_colors(theme_index)
    if colors is None:
        return None

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, colors["window"])
    palette.setColor(QPalette.ColorRole.WindowText, colors["window_text"])
    palette.setColor(QPalette.ColorRole.Base, colors["base"])
    palette.setColor(QPalette.ColorRole.AlternateBase, colors["alternate_base"])
    palette.setColor(QPalette.ColorRole.ToolTipBase, colors["tooltip_base"])
    palette.setColor(QPalette.ColorRole.ToolTipText, colors["tooltip_text"])
    palette.setColor(QPalette.ColorRole.Text, colors["text"])
    palette.setColor(QPalette.ColorRole.PlaceholderText, colors["placeholder"])
    palette.setColor(QPalette.ColorRole.Button, colors["button"])
    palette.setColor(QPalette.ColorRole.ButtonText, colors["button_text"])
    palette.setColor(QPalette.ColorRole.BrightText, colors["bright_text"])
    palette.setColor(QPalette.ColorRole.Highlight, colors["highlight"])
    palette.setColor(QPalette.ColorRole.HighlightedText, colors["highlighted_text"])
    palette.setColor(QPalette.ColorRole.Link, colors["link"])
    palette.setColor(QPalette.ColorRole.LinkVisited, colors["link_visited"])
    palette.setColor(QPalette.ColorRole.Mid, colors["mid"])
    palette.setColor(QPalette.ColorRole.Dark, colors["dark"])
    palette.setColor(QPalette.ColorRole.Shadow, colors["shadow"])

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        colors["disabled_text"],
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        colors["disabled_text"],
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        colors["disabled_text"],
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Highlight,
        colors["mid"],
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.HighlightedText,
        colors["window_text"],
    )
    return palette


def contrast_text_color(background: QColor) -> QColor:
    brightness = (
        background.red() * 0.299
        + background.green() * 0.587
        + background.blue() * 0.114
    )
    return QColor(17, 24, 39) if brightness > 186 else QColor(248, 250, 252)


def rgba_css(color: QColor, alpha: Optional[int] = None) -> str:
    resolved_alpha = color.alpha() if alpha is None else alpha
    return "rgba({0}, {1}, {2}, {3})".format(
        color.red(), color.green(), color.blue(), resolved_alpha
    )


def text_color_stylesheet(color: QColor) -> str:
    return "color: {0};".format(color.name())


def status_input_stylesheet(color: QColor) -> str:
    border_color = color.lighter(115) if color.lightness() < 128 else color.darker(115)
    return (
        "background-color: {0}; border: 1px solid {1}; border-radius: 4px;"
    ).format(rgba_css(color, 48), border_color.name())
