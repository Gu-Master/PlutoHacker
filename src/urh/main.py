#!/usr/bin/env python3

import locale
import multiprocessing
import os
import re
import sys

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPalette, QIcon
from PyQt6.QtWidgets import QApplication, QWidget, QStyleFactory

# noinspection PyUnresolvedReferences
import urh.ui.urh_rc

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error as e:
    print("Ignoring locale error {}".format(e))

GENERATE_UI = True


def fix_windows_stdout_stderr():
    """
    Processes can't write to stdout/stderr on frozen windows apps because they do not exist here
    if process tries it anyway we get a nasty dialog window popping up, so we redirect the streams to a dummy
    needed for frozen Windows builds without a console
    """

    if hasattr(sys, "frozen") and sys.platform == "win32":
        try:
            sys.stdout.write("\n")
            sys.stdout.flush()
        except:

            class DummyStream(object):
                def __init__(self):
                    pass

                def write(self, data):
                    pass

                def read(self, data):
                    pass

                def flush(self):
                    pass

                def close(self):
                    pass

            sys.stdout, sys.stderr, sys.stdin = (
                DummyStream(),
                DummyStream(),
                DummyStream(),
            )
            sys.__stdout__, sys.__stderr__, sys.__stdin__ = (
                DummyStream(),
                DummyStream(),
                DummyStream(),
            )


def main():
    fix_windows_stdout_stderr()

    if sys.version_info < (3, 9):
        print("You need at least Python 3.9 for this application!")
        sys.exit(1)

    urh_exe = sys.executable if hasattr(sys, "frozen") else sys.argv[0]
    urh_exe = os.readlink(urh_exe) if os.path.islink(urh_exe) else urh_exe

    urh_dir = os.path.join(os.path.dirname(os.path.realpath(urh_exe)), "..", "..")
    prefix = os.path.abspath(os.path.normpath(urh_dir))

    src_dir = os.path.join(prefix, "src")
    if (
        os.path.exists(src_dir)
        and not prefix.startswith("/usr")
        and not re.match(r"(?i)c:\\program", prefix)
    ):
        # Started locally, not installed -> add directory to path
        sys.path.insert(0, src_dir)

    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        import urh.version

        print(urh.version.VERSION)
        sys.exit(0)

    if GENERATE_UI and not hasattr(sys, "frozen"):
        try:
            sys.path.insert(0, prefix)
            from data import generate_ui

            generate_ui.gen()
        except (ImportError, FileNotFoundError):
            # The generate UI script cannot be found so we are most likely in release mode, no problem here.
            pass

    from urh.util import util

    util.set_shared_library_path()

    try:
        import urh.cythonext.signal_functions
        import urh.cythonext.path_creator
        import urh.cythonext.util
    except ImportError:
        if hasattr(sys, "frozen"):
            print("C++ Extensions not found. Exiting...")
            sys.exit(1)
        print("Could not find C++ extensions, trying to build them.")
        old_dir = os.path.realpath(os.curdir)
        os.chdir(os.path.join(src_dir, "urh", "cythonext"))

        from urh.cythonext import build

        build.main()

        os.chdir(old_dir)

    from urh import settings
    from urh.controller.MainController import MainController
    from urh.ui import themes, icon_theme

    theme_index = themes.read_theme_index()

    if theme_index > 0:
        os.environ["QT_QPA_PLATFORMTHEME"] = "fusion"

    app = QApplication(["PlutoSDR Protocol Tool"] + sys.argv[1:])
    app.setWindowIcon(QIcon(":/icons/icons/appicon.png"))
    icon_theme.install_custom_icon_theme()

    try:
        app.styleHints().setShowShortcutsInContextMenus(True)
    except AttributeError:
        pass

    util.set_icon_theme()

    font_size = settings.read("font_size", 0, float)
    if font_size > 0:
        font = app.font()
        font.setPointSizeF(font_size)
        app.setFont(font)

    settings.write("default_theme", app.style().objectName())

    if theme_index > 0:
        app.setStyle(QStyleFactory.create("Fusion"))
        palette = themes.build_application_palette(theme_index)
        if palette is not None:
            app.setPalette(palette)

    # use system colors for painting
    widget = QWidget()
    bg_color = widget.palette().color(QPalette.ColorRole.Window)
    fg_color = widget.palette().color(QPalette.ColorRole.WindowText)
    selection_color = widget.palette().color(QPalette.ColorRole.Highlight)
    settings.BGCOLOR = bg_color
    settings.LINECOLOR = fg_color
    settings.SELECTION_COLOR = selection_color
    settings.SEND_INDICATOR_COLOR = selection_color

    # allow usage of prange (OpenMP) in Processes
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    main_window = MainController()

    if sys.platform == "win32":
        # Ensure we get the app icon in windows taskbar
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ia232.plutosdr_protocol_tool"
        )

    if settings.read("MainController/geometry", type=bytes):
        main_window.show()
    else:
        main_window.showMaximized()

    if "autoclose" in sys.argv[1:]:
        # Autoclose after 1 second, this is useful for automated testing
        timer = QTimer()
        timer.timeout.connect(app.quit)
        timer.start(1000)

    return_code = app.exec()
    app.closeAllWindows()
    os._exit(
        return_code
    )  # sys.exit() is not enough on Windows and will result in crash on exit


if __name__ == "__main__":
    if hasattr(sys, "frozen"):
        multiprocessing.freeze_support()

    main()
