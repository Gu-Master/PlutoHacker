import os
import sys

import psutil
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor

from urh.util.Formatter import Formatter
from urh.util.Logger import logger


global __qt_settings


def __get_qt_settings():
    global __qt_settings

    try:
        __qt_settings.fileName()
    except:
        __qt_settings = QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, "urh", "urh"
        )

    return __qt_settings


def get_qt_settings_filename():
    return __get_qt_settings().fileName()


MAX_RECENT_FILE_NR = 10
ZOOM_TICKS = 10

PIXELS_PER_PATH = 5000

SPECTRUM_BUFFER_SIZE = 2**15
SNIFF_BUFFER_SIZE = 5 * 10**7
CONTINUOUS_BUFFER_SIZE_MB = 50

PAUSE_TRESHOLD = 10
RECT_BIT_WIDTH = 10
BIT_SCENE_HEIGHT = 100

TRANSPARENT_COLOR = QColor(Qt.GlobalColor.transparent)

LINECOLOR = QColor.fromRgb(231, 237, 245)
LINECOLOR_I = QColor.fromRgb(56, 189, 248)
LINECOLOR_Q = QColor.fromRgb(245, 158, 11)
BGCOLOR = QColor.fromRgb(18, 24, 38)
AXISCOLOR = QColor.fromRgb(148, 163, 184, 110)
ARROWCOLOR = QColor.fromRgb(230, 168, 72)

ERROR_BG_COLOR = QColor.fromRgb(248, 113, 113, 150)

SEND_INDICATOR_COLOR = QColor.fromRgb(230, 168, 72)  # overwritten by system color

# ROI-SELECTION COLORS
SELECTION_COLOR = QColor.fromRgb(230, 168, 72)  # overwritten by system color
NOISE_COLOR = QColor.fromRgb(244, 114, 182)
SELECTION_OPACITY = 1
NOISE_OPACITY = 0.33

# SEPARATION COLORS
ONES_AREA_COLOR = Qt.GlobalColor.green
ZEROS_AREA_COLOR = Qt.GlobalColor.magenta
SEPARATION_OPACITY = 0.15
SEPARATION_PADDING = 0.05  # percent

# PROTOCOL TABLE COLORS
SELECTED_ROW_COLOR = QColor.fromRgb(230, 168, 72)
DIFFERENCE_CELL_COLOR = QColor.fromRgb(248, 113, 113)

PROPERTY_FOUND_COLOR = QColor.fromRgb(74, 222, 128, 100)
PROPERTY_NOT_FOUND_COLOR = QColor.fromRgb(248, 113, 113, 100)

SEPARATION_ROW_HEIGHT = 30

PROJECT_FILE = "PlutoSDRProject.xml"
DECODINGS_FILE = "decodings.txt"
FIELD_TYPE_SETTINGS = os.path.realpath(
    os.path.join(get_qt_settings_filename(), "..", "fieldtypes.xml")
)

# DEVICE SETTINGS
DEFAULT_IP_PLUTOSDR = "192.168.2.1"

# DECODING NAMES
DECODING_INVERT = "Invert"
DECODING_DIFFERENTIAL = "Differential Encoding"
DECODING_REDUNDANCY = "Remove Redundancy"
DECODING_DATAWHITENING = "Remove Data Whitening (CC1101)"
DECODING_CARRIER = "Remove Carrier"
DECODING_BITORDER = "Change Bitorder"
DECODING_EDGE = "Edge Trigger"
DECODING_SUBSTITUTION = "Substitution"
DECODING_EXTERNAL = "External Program"
DECODING_ENOCEAN = "Wireless Short Packet (WSP)"
DECODING_CUT = "Cut before/after"
DECODING_MORSE = "Morse Code"
DECODING_DISABLED_PREFIX = "[Disabled] "

def _label_color(r: int, g: int, b: int):
    return QColor.fromRgb(r, g, b, 125)


LABEL_COLORS = [
    _label_color(56, 189, 248),  # sky
    _label_color(16, 185, 129),  # emerald
    _label_color(248, 113, 113),  # coral
    _label_color(129, 140, 248),  # indigo
    _label_color(245, 158, 11),  # amber
    _label_color(244, 114, 182),  # pink
    _label_color(45, 212, 191),  # teal
    _label_color(132, 204, 22),  # lime
    _label_color(250, 204, 21),  # yellow
    _label_color(100, 116, 139),  # slate
    _label_color(96, 165, 250),  # blue
    _label_color(192, 132, 252),  # violet
    _label_color(110, 231, 183),  # mint
    _label_color(203, 213, 225),  # silver
    _label_color(251, 146, 60),  # orange
    _label_color(34, 211, 238),  # cyan
    _label_color(253, 224, 71),  # warm yellow
    _label_color(71, 85, 105),  # steel
    _label_color(251, 191, 36),  # sunflower
    _label_color(147, 197, 253),  # light blue
    _label_color(20, 184, 166),  # aqua
    _label_color(74, 222, 128),  # success green
    _label_color(217, 70, 239),  # magenta
    _label_color(163, 230, 53),  # chartreuse
    _label_color(249, 168, 212),  # pastel pink
]

# full alpha for participant colors, since its used in text html view (signal frame)
PARTICIPANT_COLORS = [
    QColor.fromRgb(lc.red(), lc.green(), lc.blue()) for lc in LABEL_COLORS
]

BG_COLOR_CORRECT = QColor(74, 222, 128, 150)
BG_COLOR_WRONG = QColor(248, 113, 113, 150)

HIGHLIGHT_TEXT_BACKGROUND_COLOR = QColor(230, 168, 72)
HIGHLIGHT_TEXT_FOREGROUND_COLOR = QColor(16, 22, 34)

PEAK_COLOR = QColor(251, 146, 60)

NUM_CENTERS = 16

SHORTEST_PREAMBLE_IN_BITS = 8
SHORTEST_CONSTANT_IN_BITS = 8

# used for displaying indented logs e.g. in simulation dialog
INDENT = 8

# Pause separator in message files
PAUSE_SEP = "/"


def read(key: str, default_value=None, type=str):
    val = __get_qt_settings().value(key, default_value)
    if val is None:
        val = type()

    if type is bool:
        val = str(val).lower()
        try:
            return bool(int(val))
        except ValueError:
            return str(val).lower() == "true"
    else:
        return type(val)


def write(key: str, value):
    __get_qt_settings().setValue(key, value)


def all_keys():
    return __get_qt_settings().allKeys()


def sync():
    __get_qt_settings().sync()


OVERWRITE_RECEIVE_BUFFER_SIZE = None


def get_receive_buffer_size(
    resume_on_full_receive_buffer: bool, spectrum_mode: bool
) -> int:
    if OVERWRITE_RECEIVE_BUFFER_SIZE:
        return OVERWRITE_RECEIVE_BUFFER_SIZE

    if resume_on_full_receive_buffer:
        if spectrum_mode:
            num_samples = SPECTRUM_BUFFER_SIZE
        else:
            num_samples = SNIFF_BUFFER_SIZE
    else:
        # Take 60% of avail memory
        threshold = read("ram_threshold", 0.6, float)
        num_samples = threshold * (psutil.virtual_memory().available / 8)

    # Do not let it allocate too much memory on 32 bit
    if 8 * 2 * num_samples > sys.maxsize:
        num_samples = sys.maxsize // (8 * 2 * 1.5)
        logger.info("Correcting buffer size to {}".format(num_samples))

    logger.info(
        "Allocate receive buffer with {0}B".format(
            Formatter.big_value_with_suffix(num_samples * 8)
        )
    )
    return int(num_samples)
