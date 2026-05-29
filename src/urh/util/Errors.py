import traceback

from PyQt6.QtWidgets import QMessageBox, QWidget

from urh.util.Formatter import Formatter
from urh.util.Logger import logger


class Errors:
    @staticmethod
    def generic_error(title: str, msg: str, detailed_msg: str = None):
        w = QWidget()
        if detailed_msg:
            msg = (
                "Error: <b>"
                + msg.replace("\n", "<br>")
                + "</b>"
                + "<br><br>----------<br><br>"
                + detailed_msg.replace("\n", "<br>")
            )
        QMessageBox.critical(w, title, msg)

    @staticmethod
    def exception(exception: Exception):
        logger.exception(exception)
        w = QWidget()
        msg = "Error: <b>" + str(exception).replace("\n", "<br>") + "</b><hr>"
        msg += traceback.format_exc().replace("\n", "<br>")
        QMessageBox.critical(w, "An error occurred", msg)

    @staticmethod
    def no_device():
        w = QWidget()
        QMessageBox.critical(
            w,
            w.tr("No devices"),
            w.tr(
                "You have to choose at least one available "
                "device in Edit->Options->Device."
            ),
        )

    @staticmethod
    def empty_selection():
        w = QWidget()
        QMessageBox.critical(w, w.tr("No selection"), w.tr("Your selection is empty!"))

    @staticmethod
    def write_error(msg):
        w = QWidget()
        QMessageBox.critical(
            w,
            w.tr("Write error"),
            w.tr("There was a error writing this file! {0}".format(msg)),
        )

    @staticmethod
    def plutosdr_not_found():
        w = QWidget()
        QMessageBox.critical(
            w,
            w.tr("PlutoSDR not found"),
            w.tr(
                "Could not find a connected PlutoSDR. Check USB/network connection "
                "and make sure libiio can discover the device."
            ),
        )

    @staticmethod
    def empty_group():
        w = QWidget()
        QMessageBox.critical(
            w, w.tr("Empty group"), w.tr("The group may not be empty.")
        )

    @staticmethod
    def invalid_path(path: str):
        w = QWidget()
        QMessageBox.critical(
            w, w.tr("Invalid Path"), w.tr("The path {0} is invalid.".format(path))
        )

    @staticmethod
    def not_enough_ram_for_sending_precache(memory_size_bytes):
        w = QWidget()
        if memory_size_bytes:
            msg = (
                "Precaching all your modulated data would take <b>{0}B</b> of memory, "
                "which does not fit into your RAM.<br>".format(
                    Formatter.big_value_with_suffix(memory_size_bytes)
                )
            )
        else:
            msg = ""

        msg += (
            "Sending will be done in <b>continuous mode</b>.<br><br>"
            "This means, modulation will be performed live during sending.<br><br>"
            "If you experience problems, "
            "consider sending less messages or upgrade your RAM."
        )

        QMessageBox.information(w, w.tr("Entering continuous send mode"), w.tr(msg))
