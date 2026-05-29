from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


_ORIGINAL_FROM_THEME = QIcon.fromTheme
_INSTALLED = False


ICON_SPECS = {
    "list-add": ("add", "#3b82f6"),
    "document-new": ("add", "#3b82f6"),
    "list-remove": ("remove", "#ef4444"),
    "edit-delete": ("delete", "#ef4444"),
    "media-record": ("record", "#ef4444"),
    "media-playback-stop": ("stop", "#ef4444"),
    "media-playback-start": ("play", "#16a34a"),
    "media-playback-pause": ("pause", "#f59e0b"),
    "document-save": ("save", "#0f766e"),
    "document-save-as": ("save", "#0f766e"),
    "document-open": ("open", "#2563eb"),
    "document-import": ("import", "#2563eb"),
    "folder-open": ("folder_open", "#8b5cf6"),
    "folder-new": ("folder_plus", "#8b5cf6"),
    "folder": ("folder", "#8b5cf6"),
    "view-refresh": ("refresh", "#0891b2"),
    "configure": ("settings", "#7c3aed"),
    "help-contents": ("help", "#2563eb"),
    "help-about": ("info", "#2563eb"),
    "dialog-information": ("info", "#2563eb"),
    "window-close": ("close", "#ef4444"),
    "document-close": ("close", "#ef4444"),
    "application-exit": ("exit", "#ef4444"),
    "dialog-cancel": ("close", "#ef4444"),
    "edit-undo": ("undo", "#2563eb"),
    "edit-redo": ("redo", "#2563eb"),
    "go-previous": ("left", "#2563eb"),
    "go-next": ("right", "#2563eb"),
    "go-up": ("up", "#2563eb"),
    "go-down": ("down", "#2563eb"),
    "edit-find": ("search", "#0891b2"),
    "view-filter": ("filter", "#0891b2"),
    "edit-select-all": ("select_all", "#0891b2"),
    "zoom-in": ("zoom_in", "#0f766e"),
    "zoom-out": ("zoom_out", "#0f766e"),
    "zoom-original": ("zoom_reset", "#0f766e"),
    "zoom-fit-best": ("zoom_fit", "#0f766e"),
    "zoom-select": ("search", "#0891b2"),
    "edit-copy": ("copy", "#0f766e"),
    "edit-paste": ("paste", "#0f766e"),
    "text-csv": ("csv", "#0f766e"),
    "view-sort-ascending": ("sort", "#2563eb"),
    "align-horizontal-left": ("align_left", "#2563eb"),
    "utilities-log-viewer": ("log", "#2563eb"),
    "edit-table-insert-column-left": ("table_left", "#7c3aed"),
    "edit-table-insert-column-right": ("table_right", "#7c3aed"),
}


def install_custom_icon_theme():
    global _INSTALLED
    if _INSTALLED:
        return

    def _custom_from_theme(name: str, fallback: QIcon | None = None):
        if name.startswith(":/"):
            return QIcon(name)

        icon = custom_icon_for_name(name)
        if not icon.isNull():
            return icon

        if fallback is None:
            return _ORIGINAL_FROM_THEME(name)
        return _ORIGINAL_FROM_THEME(name, fallback)

    QIcon.fromTheme = staticmethod(_custom_from_theme)
    _INSTALLED = True


def get_icon(name: str) -> QIcon:
    return custom_icon_for_name(name)


def custom_icon_for_name(name: str) -> QIcon:
    spec = ICON_SPECS.get(name)
    if spec is None:
        return QIcon()
    return _build_icon(spec[0], spec[1])


@lru_cache(maxsize=128)
def _build_icon(symbol: str, color_hex: str) -> QIcon:
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    bg = QColor(color_hex)
    border = bg.darker(125)
    fg = QColor("#ffffff")

    painter.setBrush(bg)
    painter.setPen(QPen(border, 2.4))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 16, 16)

    _draw_symbol(painter, symbol, fg)

    painter.end()
    return QIcon(pixmap)


def _set_stroke(painter: QPainter, color: QColor, width: float = 4.8):
    pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)


def _draw_symbol(painter: QPainter, symbol: str, color: QColor):
    if symbol == "add":
        _set_stroke(painter, color)
        painter.drawLine(32, 18, 32, 46)
        painter.drawLine(18, 32, 46, 32)
    elif symbol == "remove":
        _set_stroke(painter, color)
        painter.drawLine(18, 32, 46, 32)
    elif symbol == "record":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(18, 18, 28, 28))
    elif symbol == "stop":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(18, 18, 28, 28), 5, 5)
    elif symbol == "play":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        path = QPainterPath()
        path.moveTo(24, 18)
        path.lineTo(46, 32)
        path.lineTo(24, 46)
        path.closeSubpath()
        painter.drawPath(path)
    elif symbol == "pause":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(20, 18, 9, 28), 3, 3)
        painter.drawRoundedRect(QRectF(35, 18, 9, 28), 3, 3)
    elif symbol == "save":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        path = QPainterPath()
        path.moveTo(20, 16)
        path.lineTo(40, 16)
        path.lineTo(46, 22)
        path.lineTo(46, 48)
        path.lineTo(18, 48)
        path.lineTo(18, 18)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setBrush(QColor("#0f172a"))
        painter.drawRect(QRectF(23, 19, 14, 8))
        painter.setBrush(QColor("#dbeafe"))
        painter.drawRect(QRectF(23, 32, 18, 10))
    elif symbol in {"open", "import", "folder", "folder_open", "folder_plus"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        body = QPainterPath()
        body.moveTo(14, 24)
        body.lineTo(26, 24)
        body.lineTo(31, 19)
        body.lineTo(50, 19)
        body.lineTo(50, 26)
        body.lineTo(18, 26)
        body.lineTo(14, 40)
        body.lineTo(48, 40)
        body.lineTo(52, 24)
        body.closeSubpath()
        painter.drawPath(body)
        if symbol == "folder_open":
            _set_stroke(painter, QColor("#0f172a"), 3.5)
            painter.drawLine(22, 45, 30, 37)
            painter.drawLine(30, 37, 38, 45)
        elif symbol == "folder_plus":
            _set_stroke(painter, QColor("#0f172a"), 3.5)
            painter.drawLine(35, 30, 35, 44)
            painter.drawLine(28, 37, 42, 37)
    elif symbol == "refresh":
        _set_stroke(painter, color)
        painter.drawArc(QRectF(16, 16, 32, 32), 35 * 16, 275 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        path = QPainterPath()
        path.moveTo(45, 16)
        path.lineTo(50, 26)
        path.lineTo(39, 25)
        path.closeSubpath()
        painter.drawPath(path)
    elif symbol == "settings":
        _set_stroke(painter, color, 4.2)
        painter.drawLine(20, 20, 44, 20)
        painter.drawLine(20, 32, 44, 32)
        painter.drawLine(20, 44, 44, 44)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(26, 15, 10, 10))
        painter.drawEllipse(QRectF(34, 27, 10, 10))
        painter.drawEllipse(QRectF(22, 39, 10, 10))
    elif symbol in {"left", "right", "up", "down", "undo", "redo"}:
        _set_stroke(painter, color, 5.4)
        if symbol in {"left", "undo"}:
            painter.drawLine(42, 18, 22, 32)
            painter.drawLine(22, 32, 42, 46)
        elif symbol in {"right", "redo"}:
            painter.drawLine(22, 18, 42, 32)
            painter.drawLine(42, 32, 22, 46)
        elif symbol == "up":
            painter.drawLine(18, 40, 32, 20)
            painter.drawLine(32, 20, 46, 40)
        elif symbol == "down":
            painter.drawLine(18, 24, 32, 44)
            painter.drawLine(32, 44, 46, 24)
        if symbol == "undo":
            painter.drawLine(24, 32, 47, 32)
        elif symbol == "redo":
            painter.drawLine(17, 32, 40, 32)
    elif symbol == "search":
        _set_stroke(painter, color, 4.6)
        painter.drawEllipse(QRectF(17, 17, 22, 22))
        painter.drawLine(36, 36, 46, 46)
    elif symbol == "filter":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        path = QPainterPath()
        path.moveTo(16, 18)
        path.lineTo(48, 18)
        path.lineTo(36, 31)
        path.lineTo(36, 46)
        path.lineTo(28, 42)
        path.lineTo(28, 31)
        path.closeSubpath()
        painter.drawPath(path)
    elif symbol in {"help", "info"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(14, 14, 36, 36))
        painter.setPen(QPen(QColor("#0f172a"), 1.2))
        font = QFont("DejaVu Sans", 20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(14, 14, 36, 36), Qt.AlignmentFlag.AlignCenter, "?" if symbol == "help" else "i")
    elif symbol in {"close", "exit", "delete"}:
        _set_stroke(painter, color, 5.2)
        painter.drawLine(20, 20, 44, 44)
        painter.drawLine(44, 20, 20, 44)
        if symbol == "delete":
            painter.drawLine(18, 15, 46, 15)
    elif symbol in {"zoom_in", "zoom_out", "zoom_reset", "zoom_fit"}:
        _set_stroke(painter, color, 4.4)
        painter.drawEllipse(QRectF(16, 16, 20, 20))
        painter.drawLine(33, 33, 45, 45)
        if symbol == "zoom_in":
            painter.drawLine(26, 20, 26, 32)
            painter.drawLine(20, 26, 32, 26)
        elif symbol == "zoom_out":
            painter.drawLine(20, 26, 32, 26)
        elif symbol == "zoom_reset":
            painter.drawLine(20, 26, 32, 26)
            painter.drawLine(26, 20, 26, 32)
            painter.drawRect(QRectF(38, 17, 8, 8))
        elif symbol == "zoom_fit":
            painter.drawRect(QRectF(38, 17, 9, 9))
            painter.drawRect(QRectF(17, 38, 9, 9))
    elif symbol == "copy":
        _set_stroke(painter, color, 4.0)
        painter.drawRoundedRect(QRectF(18, 22, 18, 20), 3, 3)
        painter.drawRoundedRect(QRectF(28, 14, 18, 20), 3, 3)
    elif symbol == "paste":
        _set_stroke(painter, color, 4.0)
        painter.drawRoundedRect(QRectF(20, 18, 24, 28), 4, 4)
        painter.drawLine(26, 14, 38, 14)
        painter.drawLine(26, 28, 38, 28)
        painter.drawLine(26, 36, 38, 36)
    elif symbol == "csv":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(14, 14, 36, 36), 8, 8)
        painter.setPen(QPen(QColor("#0f172a"), 1.2))
        font = QFont("DejaVu Sans", 12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(14, 14, 36, 36), Qt.AlignmentFlag.AlignCenter, "CSV")
    elif symbol == "sort":
        _set_stroke(painter, color, 4.4)
        painter.drawLine(20, 42, 20, 18)
        painter.drawLine(20, 18, 14, 24)
        painter.drawLine(20, 18, 26, 24)
        painter.drawLine(30, 42, 46, 42)
        painter.drawLine(34, 32, 46, 32)
        painter.drawLine(38, 22, 46, 22)
    elif symbol == "align_left":
        _set_stroke(painter, color, 4.2)
        painter.drawLine(18, 20, 46, 20)
        painter.drawLine(18, 30, 38, 30)
        painter.drawLine(18, 40, 44, 40)
    elif symbol == "log":
        _set_stroke(painter, color, 4.2)
        painter.drawRoundedRect(QRectF(18, 16, 28, 32), 5, 5)
        painter.drawLine(24, 24, 40, 24)
        painter.drawLine(24, 32, 40, 32)
        painter.drawLine(24, 40, 34, 40)
    elif symbol in {"table_left", "table_right"}:
        _set_stroke(painter, color, 3.8)
        painter.drawRect(QRectF(16, 18, 32, 28))
        painter.drawLine(26, 18, 26, 46)
        painter.drawLine(38, 18, 38, 46)
        if symbol == "table_left":
            painter.drawLine(10, 32, 20, 32)
            painter.drawLine(15, 27, 15, 37)
        else:
            painter.drawLine(44, 32, 54, 32)
            painter.drawLine(49, 27, 49, 37)
    elif symbol == "select_all":
        _set_stroke(painter, color, 4.2)
        painter.drawRect(QRectF(16, 16, 18, 18))
        painter.drawRect(QRectF(30, 30, 18, 18))
    else:
        painter.setPen(QPen(color, 1.0))
        font = QFont("DejaVu Sans", 22)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(8, 8, 48, 48), Qt.AlignmentFlag.AlignCenter, symbol[:1].upper())
