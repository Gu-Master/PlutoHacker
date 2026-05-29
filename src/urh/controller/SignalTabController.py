import os

from PyQt6.QtCore import QPoint, pyqtSignal, pyqtSlot, Qt, QSize, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QSizePolicy,
    QCheckBox,
    QMessageBox,
    QListWidgetItem,
)
from PyQt6.QtGui import QUndoStack

from urh import settings
from urh.controller.widgets.SignalFrame import SignalFrame
from urh.signalprocessing.Signal import Signal
from urh.ui import icon_theme
from urh.ui.ui_tab_interpretation import Ui_Interpretation
from urh.util import util


class SignalTabController(QWidget):
    frame_closed = pyqtSignal(SignalFrame)
    not_show_again_changed = pyqtSignal()
    signal_created = pyqtSignal(int, Signal)
    files_dropped = pyqtSignal(list)
    frame_was_dropped = pyqtSignal(int, int)
    record_signal_requested = pyqtSignal()
    open_signal_requested = pyqtSignal()
    choose_folder_requested = pyqtSignal()

    @property
    def num_frames(self):
        return len(self.signal_frames)

    @property
    def signal_frames(self):
        """

        :rtype: list of SignalFrame
        """
        splitter = self.ui.splitter
        return [
            splitter.widget(i)
            for i in range(splitter.count())
            if isinstance(splitter.widget(i), SignalFrame)
        ]

    @property
    def signal_undo_stack(self):
        return self.undo_stack

    def __init__(self, project_manager, parent=None):
        super().__init__(parent)
        self.ui = Ui_Interpretation()
        self.ui.setupUi(self)

        util.set_splitter_stylesheet(self.ui.splitter)

        self.ui.placeholderLabel.setVisible(False)
        self.ui.splitterMain.setStretchFactor(0, 0)
        self.ui.splitterMain.setStretchFactor(1, 1)
        self.ui.splitterMain.setSizes([300, 900])
        self.ui.splitter.setStretchFactor(0, 4)
        self.ui.splitter.setStretchFactor(1, 2)
        self.ui.listWidgetSignals.setUniformItemSizes(True)
        self.ui.listWidgetSignals.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.getting_started_status = None
        self.__set_getting_started_status(True)

        self.undo_stack = QUndoStack()
        self.project_manager = project_manager

        self.drag_pos = None

        self.ui.listWidgetSignals.currentRowChanged.connect(
            self.on_signal_list_current_row_changed
        )
        self.ui.btnRecordSignal.clicked.connect(self.record_signal_requested.emit)
        self.ui.btnOpenSignalFiles.clicked.connect(self.open_signal_requested.emit)
        self.ui.btnChooseSignalFolder.clicked.connect(self.choose_folder_requested.emit)
        self.__apply_sidebar_icons()

    def __apply_sidebar_icons(self):
        icon_size = QSize(18, 18)
        self.ui.btnRecordSignal.setIcon(icon_theme.get_icon("media-record"))
        self.ui.btnRecordSignal.setIconSize(icon_size)
        self.ui.btnOpenSignalFiles.setIcon(icon_theme.get_icon("document-open"))
        self.ui.btnOpenSignalFiles.setIconSize(icon_size)
        self.ui.btnChooseSignalFolder.setIcon(icon_theme.get_icon("folder-open"))
        self.ui.btnChooseSignalFolder.setIconSize(icon_size)

    def on_files_dropped(self, files):
        self.files_dropped.emit(files)

    def close_frame(self, frame: SignalFrame):
        self.frame_closed.emit(frame)

    def add_signal_frame(self, proto_analyzer, index=-1):
        self.__set_getting_started_status(False)
        sig_frame = SignalFrame(
            proto_analyzer, self.undo_stack, self.project_manager, parent=self
        )
        sframes = self.signal_frames

        if len(proto_analyzer.signal.filename) == 0:
            # new signal from "create signal from selection"
            sig_frame.ui.btnSaveSignal.show()

        self.__create_connects_for_signal_frame(signal_frame=sig_frame)
        sig_frame.signal_created.connect(self.emit_signal_created)
        sig_frame.not_show_again_changed.connect(self.not_show_again_changed.emit)
        sig_frame.ui.lineEditSignalName.textChanged.connect(
            lambda _text, frame=sig_frame: self.update_list_entry_for_frame(frame)
        )
        sig_frame.ui.lineEditSignalName.setToolTip(
            self.tr("Sourcefile: ") + proto_analyzer.signal.filename
        )
        sig_frame.apply_to_all_clicked.connect(self.on_apply_to_all_clicked)

        prev_signal_frame = sframes[-1] if len(sframes) > 0 else None
        if prev_signal_frame is not None and hasattr(prev_signal_frame, "ui"):
            sig_frame.ui.cbProtoView.setCurrentIndex(
                prev_signal_frame.ui.cbProtoView.currentIndex()
            )

        sig_frame.blockSignals(True)

        index = self.num_frames if index == -1 else index
        sig_frame.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        self.ui.splitter.insertWidget(index, sig_frame)
        sig_frame.blockSignals(False)

        self.add_signal_to_list(sig_frame, index)

        default_view = settings.read("default_view", 0, int)
        sig_frame.ui.cbProtoView.setCurrentIndex(default_view)
        self.select_signal_frame(sig_frame)

        return sig_frame

    def add_empty_frame(self, filename: str, proto):
        self.__set_getting_started_status(False)
        sig_frame = SignalFrame(
            proto_analyzer=proto,
            undo_stack=self.undo_stack,
            project_manager=self.project_manager,
            parent=self,
        )

        sig_frame.ui.lineEditSignalName.setText(filename)
        self.__create_connects_for_signal_frame(signal_frame=sig_frame)
        sig_frame.ui.lineEditSignalName.textChanged.connect(
            lambda _text, frame=sig_frame: self.update_list_entry_for_frame(frame)
        )

        self.ui.splitter.insertWidget(self.num_frames, sig_frame)
        self.add_signal_to_list(sig_frame, self.num_frames - 1)
        self.select_signal_frame(sig_frame)

        return sig_frame

    def __set_getting_started_status(self, getting_started: bool):
        if getting_started == self.getting_started_status:
            return

        self.getting_started_status = getting_started
        self.ui.labelGettingStarted.setVisible(getting_started)

        if not getting_started:
            w = QWidget()
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self.ui.splitter.addWidget(w)

    def __create_connects_for_signal_frame(self, signal_frame: SignalFrame):
        signal_frame.hold_shift = settings.read("hold_shift_to_drag", True, type=bool)
        signal_frame.drag_started.connect(self.frame_dragged)
        signal_frame.frame_dropped.connect(self.frame_dropped)
        signal_frame.files_dropped.connect(self.on_files_dropped)
        signal_frame.closed.connect(self.close_frame)

    def add_signal_to_list(self, signal_frame: SignalFrame, index: int):
        item = QListWidgetItem()
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.ui.listWidgetSignals.insertItem(index, item)
        self.update_list_entry_for_frame(signal_frame)

    def update_list_entry_for_frame(self, signal_frame: SignalFrame):
        try:
            index = self.signal_frames.index(signal_frame)
        except ValueError:
            return

        item = self.ui.listWidgetSignals.item(index)
        if item is None:
            return

        display_name = signal_frame.ui.lineEditSignalName.text().strip()
        filename = signal_frame.signal.filename if signal_frame.signal is not None else ""
        if not display_name:
            display_name = os.path.basename(filename) if filename else "Без имени"

        item.setText(display_name)
        item.setToolTip(filename or display_name)
        item.setData(Qt.ItemDataRole.UserRole, filename or display_name)

    def select_signal_frame(self, signal_frame: SignalFrame):
        try:
            index = self.signal_frames.index(signal_frame)
        except ValueError:
            return

        self.ui.listWidgetSignals.blockSignals(True)
        self.ui.listWidgetSignals.setCurrentRow(index)
        self.ui.listWidgetSignals.blockSignals(False)
        self.update_signal_meta(signal_frame)
        self.show_only_signal_frame(signal_frame)

    def show_only_signal_frame(self, selected_frame: SignalFrame | None):
        frames = self.signal_frames
        has_frames = len(frames) > 0
        self.ui.labelGettingStarted.setVisible(not has_frames or selected_frame is None)
        self.update_signal_meta(selected_frame)

        for frame in frames:
            frame.setVisible(frame is selected_frame)

        if selected_frame is not None:
            selected_frame.show()
            self.ui.scrollArea.ensureWidgetVisible(selected_frame, 0, 0)
            self.ui.scrollArea.horizontalScrollBar().setValue(0)
            self.ui.scrollArea.verticalScrollBar().setValue(0)
            QTimer.singleShot(
                0,
                lambda frame=selected_frame: self._restore_signal_frame_view(frame),
            )

    def _restore_signal_frame_view(self, signal_frame: SignalFrame):
        if signal_frame is None or signal_frame not in self.signal_frames:
            return

        self.ui.scrollArea.horizontalScrollBar().setValue(0)
        self.ui.scrollArea.verticalScrollBar().setValue(0)
        self.ui.scrollArea.ensureWidgetVisible(signal_frame.ui.lineEditSignalName, 24, 24)

    def remove_signal_frame(self, signal_frame: SignalFrame):
        try:
            index = self.signal_frames.index(signal_frame)
        except ValueError:
            return

        self.ui.listWidgetSignals.takeItem(index)

        remaining_frames = [frame for frame in self.signal_frames if frame is not signal_frame]
        if remaining_frames:
            next_index = min(index, len(remaining_frames) - 1)
            self.ui.listWidgetSignals.blockSignals(True)
            self.ui.listWidgetSignals.setCurrentRow(next_index)
            self.ui.listWidgetSignals.blockSignals(False)
            self.show_only_signal_frame(remaining_frames[next_index])
        else:
            self.ui.listWidgetSignals.clearSelection()
            self.show_only_signal_frame(None)

    def update_signal_meta(self, signal_frame: SignalFrame | None):
        if signal_frame is None or signal_frame.signal is None:
            self.ui.labelSignalMetaValue.setText(
                self.tr(
                    "Файл пока не выбран. Открой запись или выбери её в списке."
                )
            )
            return

        signal = signal_frame.signal
        filename = signal.filename or signal_frame.ui.lineEditSignalName.text().strip()
        base_name = os.path.basename(filename) if filename else self.tr("Без имени")

        try:
            file_size = os.path.getsize(filename) if filename and os.path.exists(filename) else 0
        except OSError:
            file_size = 0

        sample_rate = float(signal.sample_rate or 0)
        num_samples = int(signal.num_samples or 0)
        duration = num_samples / sample_rate if sample_rate > 0 else 0.0
        protocol_text = signal_frame.ui.txtEdProto.toPlainText().strip()
        has_detected_messages = bool(
            getattr(getattr(signal_frame, "proto_analyzer", None), "messages", [])
        )
        has_payload = (
            self.tr("есть данные")
            if protocol_text or has_detected_messages
            else self.tr("данные не определены")
        )

        lines = [
            self.tr("Файл: {0}").format(base_name),
            self.tr("Отсчётов: {0:,}").format(num_samples).replace(",", " "),
            self.tr("Длительность: {0:.3f} с").format(duration),
            self.tr("Частота дискретизации: {0:.0f} Гц").format(sample_rate)
            if sample_rate > 0
            else self.tr("Частота дискретизации: не указана"),
            self.tr("Размер файла: {0:.1f} КБ").format(file_size / 1024)
            if file_size > 0
            else self.tr("Размер файла: неизвестен"),
            self.tr("Содержимое: {0}").format(has_payload),
        ]
        self.ui.labelSignalMetaValue.setText("\n".join(lines))

    def set_frame_numbers(self):
        for i, f in enumerate(self.signal_frames):
            f.ui.lSignalNr.setText("{0:d}:".format(i + 1))

    @pyqtSlot()
    def save_all(self):
        if self.num_frames == 0:
            return

        try:
            not_show = settings.read("not_show_save_dialog", False, type=bool)
        except TypeError:
            not_show = False

        if not not_show:
            cb = QCheckBox("Don't ask me again.")
            msg_box = QMessageBox(
                QMessageBox.Icon.Question,
                self.tr("Confirm saving all signals"),
                self.tr("All changed signal files will be overwritten. OK?"),
            )
            msg_box.addButton(QMessageBox.StandardButton.Yes)
            msg_box.addButton(QMessageBox.StandardButton.No)
            msg_box.setCheckBox(cb)

            reply = msg_box.exec()
            not_show_again = cb.isChecked()
            settings.write("not_show_save_dialog", not_show_again)
            self.not_show_again_changed.emit()

            if reply != QMessageBox.StandardButton.Yes:
                return

        for f in self.signal_frames:
            if f.signal is None or f.signal.filename == "":
                continue
            f.signal.save()

    @pyqtSlot()
    def close_all(self):
        for f in self.signal_frames:
            f.my_close()

    @pyqtSlot(Signal)
    def on_apply_to_all_clicked(self, signal: Signal):
        for frame in self.signal_frames:
            if frame.signal is not None:
                frame.signal.noise_min_plot = signal.noise_min_plot
                frame.signal.noise_max_plot = signal.noise_max_plot

                frame.signal.block_protocol_update = True
                proto_needs_update = False

                if frame.signal.modulation_type != signal.modulation_type:
                    frame.signal.modulation_type = signal.modulation_type
                    proto_needs_update = True

                if frame.signal.center != signal.center:
                    frame.signal.center = signal.center
                    proto_needs_update = True

                if frame.signal.tolerance != signal.tolerance:
                    frame.signal.tolerance = signal.tolerance
                    proto_needs_update = True

                if frame.signal.noise_threshold != signal.noise_threshold:
                    frame.signal.noise_threshold_relative = (
                        signal.noise_threshold_relative
                    )
                    proto_needs_update = True

                if frame.signal.samples_per_symbol != signal.samples_per_symbol:
                    frame.signal.samples_per_symbol = signal.samples_per_symbol
                    proto_needs_update = True

                if frame.signal.pause_threshold != signal.pause_threshold:
                    frame.signal.pause_threshold = signal.pause_threshold
                    proto_needs_update = True

                if frame.signal.message_length_divisor != signal.message_length_divisor:
                    frame.signal.message_length_divisor = signal.message_length_divisor
                    proto_needs_update = True

                frame.signal.block_protocol_update = False

                if proto_needs_update:
                    frame.signal.protocol_needs_update.emit()

    @pyqtSlot(int)
    def on_signal_list_current_row_changed(self, row: int):
        if 0 <= row < len(self.signal_frames):
            self.select_signal_frame(self.signal_frames[row])
        else:
            self.show_only_signal_frame(None)

    @pyqtSlot(QPoint)
    def frame_dragged(self, pos: QPoint):
        self.drag_pos = pos

    @pyqtSlot(QPoint)
    def frame_dropped(self, pos: QPoint):
        start = self.drag_pos
        if start is None:
            return

        end = pos
        start_index = -1
        end_index = -1
        if self.num_frames > 1:
            for i, w in enumerate(self.signal_frames):
                if w.geometry().contains(start):
                    start_index = i

                if w.geometry().contains(end):
                    end_index = i

        self.swap_frames(start_index, end_index)
        self.frame_was_dropped.emit(start_index, end_index)

    @pyqtSlot(int, int)
    def swap_frames(self, from_index: int, to_index: int):
        if from_index != to_index:
            start_sig_widget = self.ui.splitter.widget(from_index)
            self.ui.splitter.insertWidget(to_index, start_sig_widget)

    @pyqtSlot()
    def on_participant_changed(self):
        for sframe in self.signal_frames:
            sframe.on_participant_changed()

    def redraw_spectrograms(self):
        for frame in self.signal_frames:
            if frame.ui.gvSpectrogram.width_spectrogram > 0:
                frame.draw_spectrogram(force_redraw=True)

    @pyqtSlot(int)
    def on_signal_list_current_row_changed(self, row: int):
        frames = self.signal_frames
        if 0 <= row < len(frames):
            self.show_only_signal_frame(frames[row])
        else:
            self.show_only_signal_frame(None)

    @pyqtSlot(Signal)
    def emit_signal_created(self, signal):
        try:
            index = self.signal_frames.index(self.sender()) + 1
        except ValueError:
            index = -1

        self.signal_created.emit(index, signal)
