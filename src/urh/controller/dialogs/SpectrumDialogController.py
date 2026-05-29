import json
import os
import time
from datetime import datetime

import numpy as np
from PyQt6.QtCore import QTimer, pyqtSlot
from PyQt6.QtGui import QWheelEvent, QIcon, QPixmap, QResizeEvent
from PyQt6.QtWidgets import QGraphicsScene

from urh.controller.dialogs.SendRecvDialog import SendRecvDialog
from urh.dev.VirtualDevice import VirtualDevice, Mode
from urh.signalprocessing.Spectrogram import Spectrogram
from urh.ui.painting.FFTSceneManager import FFTSceneManager
from urh.util import FileOperator
from urh.util.Formatter import Formatter


class SpectrumDialogController(SendRecvDialog):
    def __init__(
        self, project_manager, parent=None, testing_mode=False, embedded=False
    ):
        super().__init__(
            project_manager,
            is_tx=False,
            parent=parent,
            testing_mode=testing_mode,
            embedded=embedded,
        )

        self.graphics_view = self.ui.graphicsViewFFT
        self.update_interval = 1
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_spectrum)
        self.hide_receive_ui_items()
        self.hide_send_ui_items()

        self.setWindowTitle("Водопад и спектр")
        self.setWindowIcon(QIcon(":/icons/icons/spectrum.svg"))
        self.ui.btnStart.setToolTip(self.tr("Запустить"))
        self.ui.btnStop.setToolTip(self.tr("Остановить"))

        self.scene_manager = FFTSceneManager(
            parent=self, graphic_view=self.graphics_view
        )

        self.graphics_view.setScene(self.scene_manager.scene)
        self.graphics_view.scene_manager = self.scene_manager

        self.ui.graphicsViewSpectrogram.setScene(QGraphicsScene())
        self.__clear_spectrogram()

        self.gain_timer = QTimer(self)
        self.gain_timer.setSingleShot(True)

        self.if_gain_timer = QTimer(self)
        self.if_gain_timer.setSingleShot(True)

        self.bb_gain_timer = QTimer(self)
        self.bb_gain_timer.setSingleShot(True)

        self.auto_burst_enabled = True
        self.auto_burst_min_samples = 4096
        self.auto_burst_window_duration_sec = 0.12
        self.auto_burst_snapshot_duration_sec = 0.5
        self.auto_burst_max_snapshot_samples = 262144
        self.auto_burst_cooldown_sec = 2.0
        self.auto_burst_mean_trigger_factor = 3.0
        self.auto_burst_peak_trigger_factor = 5.5
        self.auto_burst_release_factor = 1.6
        self.auto_burst_floor_update_factor = 1.35
        self.auto_burst_floor_alpha = 0.08
        self.auto_burst_min_peak_level = 0.02
        self.auto_burst_active = False
        self.auto_burst_noise_floor = None
        self.last_auto_burst_save_ts = 0.0

        self.create_connects()
        self.device_settings_widget.update_for_new_device(overwrite_settings=False)

    def __append_status_message(self, message: str):
        current_text = self.ui.txtEditErrors.toPlainText().strip()
        if current_text:
            current_text += "\n"
        self.ui.txtEditErrors.setPlainText(current_text + message)

    def __reset_auto_burst_state(self):
        self.auto_burst_active = False
        self.auto_burst_noise_floor = None
        self.last_auto_burst_save_ts = 0.0

    def __get_auto_burst_window_size(self, duration_sec: float) -> int:
        sample_rate = max(1, int(self.device.sample_rate))
        return max(self.auto_burst_min_samples, int(sample_rate * duration_sec))

    def __get_auto_burst_snapshot(self):
        if self.device is None or self.device.data is None:
            return None

        current_index = int(self.device.current_index)
        if current_index < self.auto_burst_min_samples:
            return None

        snapshot_size = min(
            current_index,
            self.auto_burst_max_snapshot_samples,
            self.__get_auto_burst_window_size(self.auto_burst_snapshot_duration_sec),
        )
        if snapshot_size <= 0:
            return None

        start_index = max(0, current_index - snapshot_size)
        return self.device.data.subarray(start_index, current_index)

    def __update_auto_burst_noise_floor(self, mean_level: float):
        mean_level = max(mean_level, 1e-9)
        if self.auto_burst_noise_floor is None:
            self.auto_burst_noise_floor = mean_level
            return

        if mean_level <= self.auto_burst_noise_floor * self.auto_burst_floor_update_factor:
            alpha = self.auto_burst_floor_alpha
            self.auto_burst_noise_floor = (
                (1 - alpha) * self.auto_burst_noise_floor + alpha * mean_level
            )

    def __save_auto_burst_snapshot(
        self, snapshot, mean_level: float, peak_level: float, base_level: float
    ):
        now = time.time()
        timestamp = datetime.fromtimestamp(now)
        frequency_value = self.device.frequency
        sample_rate_value = self.device.sample_rate

        frequency_label = Formatter.big_value_with_suffix(frequency_value).replace(
            Formatter.local_decimal_seperator(), "_"
        )
        sample_rate_label = Formatter.big_value_with_suffix(sample_rate_value).replace(
            Formatter.local_decimal_seperator(), "_"
        )
        base_name = (
            f"auto_burst_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            f"_{frequency_label}Hz_{sample_rate_label}Sps"
        ).replace("__", "_")

        filename = FileOperator.save_signal_data_to_default_directory(
            base_name, snapshot, sample_rate=sample_rate_value
        )
        if not filename:
            return

        metadata = {
            "источник": "автозапись_всплеска_водопада",
            "устройство": self.device.name,
            "частота_гц": float(frequency_value),
            "частота_дискретизации_гц": float(sample_rate_value),
            "полоса_гц": float(self.device.bandwidth),
            "время_сохранения": timestamp.isoformat(timespec="seconds"),
            "образцов": int(snapshot.num_samples),
            "средний_уровень": float(mean_level),
            "пиковый_уровень": float(peak_level),
            "базовый_уровень": float(base_level),
            "порог_среднего": float(base_level * self.auto_burst_mean_trigger_factor),
            "порог_пика": float(
                max(
                    self.auto_burst_min_peak_level,
                    base_level * self.auto_burst_peak_trigger_factor,
                )
            ),
        }

        metadata_filename = os.path.splitext(filename)[0] + ".json"
        with open(metadata_filename, "w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, ensure_ascii=False, indent=2)

        self.__append_status_message(
            f"Автозапись всплеска: {os.path.basename(filename)}"
        )

    def __handle_auto_burst_recording(self):
        if not self.auto_burst_enabled or self.device is None or self.device.data is None:
            return

        current_index = int(self.device.current_index)
        analysis_window_size = min(
            current_index,
            self.__get_auto_burst_window_size(self.auto_burst_window_duration_sec),
        )
        if analysis_window_size < self.auto_burst_min_samples:
            return

        analysis_window = self.device.data.subarray(
            current_index - analysis_window_size, current_index
        )
        magnitudes = analysis_window.magnitudes
        if len(magnitudes) == 0:
            return

        mean_level = float(np.mean(magnitudes))
        peak_level = float(np.max(magnitudes))
        base_level = max(self.auto_burst_noise_floor or mean_level, 1e-9)

        if mean_level <= base_level * self.auto_burst_release_factor:
            self.auto_burst_active = False

        mean_trigger_level = base_level * self.auto_burst_mean_trigger_factor
        peak_trigger_level = max(
            self.auto_burst_min_peak_level,
            base_level * self.auto_burst_peak_trigger_factor,
        )
        burst_detected = (
            mean_level >= mean_trigger_level and peak_level >= peak_trigger_level
        )

        if (
            burst_detected
            and not self.auto_burst_active
            and time.time() - self.last_auto_burst_save_ts >= self.auto_burst_cooldown_sec
        ):
            snapshot = self.__get_auto_burst_snapshot()
            if snapshot is not None and snapshot.num_samples > 0:
                self.__save_auto_burst_snapshot(
                    snapshot, mean_level, peak_level, base_level
                )
                self.auto_burst_active = True
                self.last_auto_burst_save_ts = time.time()
                return

        if not burst_detected and not self.auto_burst_active:
            self.__update_auto_burst_noise_floor(mean_level)

    def __clear_spectrogram(self):
        self.ui.graphicsViewSpectrogram.scene().clear()
        window_size = Spectrogram.DEFAULT_FFT_WINDOW_SIZE
        self.ui.graphicsViewSpectrogram.scene().setSceneRect(
            0, 0, window_size, 20 * window_size
        )
        self.spectrogram_y_pos = 0
        self.ui.graphicsViewSpectrogram.fitInView(
            self.ui.graphicsViewSpectrogram.sceneRect()
        )

    def __update_spectrogram(self):
        spectrogram = Spectrogram(self.device.data)
        spectrogram.data_min = -80
        spectrogram.data_max = 10
        scene = self.ui.graphicsViewSpectrogram.scene()
        pixmap = QPixmap.fromImage(spectrogram.create_spectrogram_image(transpose=True))
        pixmap_item = scene.addPixmap(pixmap)
        pixmap_item.moveBy(0, self.spectrogram_y_pos)
        self.spectrogram_y_pos += pixmap.height()
        if self.spectrogram_y_pos >= scene.sceneRect().height():
            scene.setSceneRect(
                0, 0, Spectrogram.DEFAULT_FFT_WINDOW_SIZE, self.spectrogram_y_pos
            )
            self.ui.graphicsViewSpectrogram.ensureVisible(pixmap_item)

    def _eliminate_graphic_view(self):
        super()._eliminate_graphic_view()
        if (
            self.ui.graphicsViewSpectrogram
            and self.ui.graphicsViewSpectrogram.scene() is not None
        ):
            self.ui.graphicsViewSpectrogram.scene().clear()
            self.ui.graphicsViewSpectrogram.scene().setParent(None)
            self.ui.graphicsViewSpectrogram.setScene(None)

        self.ui.graphicsViewSpectrogram = None

    def create_connects(self):
        super().create_connects()
        self.graphics_view.freq_clicked.connect(self.on_graphics_view_freq_clicked)
        self.graphics_view.wheel_event_triggered.connect(
            self.on_graphics_view_wheel_event_triggered
        )

        self.device_settings_widget.ui.sliderGain.valueChanged.connect(
            self.on_slider_gain_value_changed
        )
        self.device_settings_widget.ui.sliderBasebandGain.valueChanged.connect(
            self.on_slider_baseband_gain_value_changed
        )
        self.device_settings_widget.ui.sliderIFGain.valueChanged.connect(
            self.on_slider_if_gain_value_changed
        )
        self.device_settings_widget.ui.spinBoxFreq.editingFinished.connect(
            self.on_spinbox_frequency_editing_finished
        )

        self.gain_timer.timeout.connect(
            self.device_settings_widget.ui.spinBoxGain.editingFinished.emit
        )
        self.if_gain_timer.timeout.connect(
            self.device_settings_widget.ui.spinBoxIFGain.editingFinished.emit
        )
        self.bb_gain_timer.timeout.connect(
            self.device_settings_widget.ui.spinBoxBasebandGain.editingFinished.emit
        )

    def resizeEvent(self, event: QResizeEvent):
        if (
            self.ui.graphicsViewSpectrogram
            and self.ui.graphicsViewSpectrogram.sceneRect()
        ):
            self.ui.graphicsViewSpectrogram.fitInView(
                self.ui.graphicsViewSpectrogram.sceneRect()
            )

    def update_view(self):
        if super().update_view():
            x, y = self.device.spectrum
            if x is None or y is None:
                return
            self.scene_manager.scene.frequencies = x
            self.scene_manager.plot_data = y
            self.scene_manager.init_scene()
            self.scene_manager.show_full_scene()
            self.graphics_view.fitInView(self.graphics_view.sceneRect())

            try:
                self.__update_spectrogram()
            except MemoryError:
                self.__clear_spectrogram()
                self.__update_spectrogram()

            self.__handle_auto_burst_recording()

    def init_device(self):
        self.device = VirtualDevice(
            self.backend_handler,
            self.selected_device_name,
            Mode.spectrum,
            device_ip="192.168.10.2",
            parent=self,
        )
        self._create_device_connects()

    @pyqtSlot(QWheelEvent)
    def on_graphics_view_wheel_event_triggered(self, event: QWheelEvent):
        self.ui.sliderYscale.wheelEvent(event)

    @pyqtSlot(float)
    def on_graphics_view_freq_clicked(self, freq: float):
        self.device_settings_widget.ui.spinBoxFreq.setValue(freq)
        self.device_settings_widget.ui.spinBoxFreq.editingFinished.emit()

    @pyqtSlot()
    def on_spinbox_frequency_editing_finished(self):
        frequency = self.device_settings_widget.ui.spinBoxFreq.value()
        self.device.frequency = frequency
        self.scene_manager.scene.center_freq = frequency
        self.scene_manager.clear_path()
        self.scene_manager.clear_peak()

    @pyqtSlot()
    def on_start_clicked(self):
        self.__reset_auto_burst_state()
        super().on_start_clicked()
        self.device.start()

    @pyqtSlot()
    def on_device_started(self):
        self.ui.graphicsViewSpectrogram.fitInView(
            self.ui.graphicsViewSpectrogram.scene().sceneRect()
        )
        super().on_device_started()
        self.device_settings_widget.ui.spinBoxPort.setEnabled(False)
        self.device_settings_widget.ui.lineEditIP.setEnabled(False)
        self.device_settings_widget.ui.cbDevice.setEnabled(False)
        self.ui.btnStart.setEnabled(False)

    @pyqtSlot()
    def on_device_stopped(self):
        self.device_settings_widget.ui.spinBoxPort.setEnabled(True)
        self.device_settings_widget.ui.lineEditIP.setEnabled(True)
        self.device_settings_widget.ui.cbDevice.setEnabled(True)

        super().on_device_stopped()

    @pyqtSlot()
    def on_clear_clicked(self):
        self.__reset_auto_burst_state()
        self.__clear_spectrogram()
        self.scene_manager.clear_path()
        self.scene_manager.clear_peak()

    @pyqtSlot(int)
    def on_slider_gain_value_changed(self, value: int):
        self.gain_timer.start(250)

    @pyqtSlot(int)
    def on_slider_if_gain_value_changed(self, value: int):
        self.if_gain_timer.start(250)

    @pyqtSlot(int)
    def on_slider_baseband_gain_value_changed(self, value: int):
        self.bb_gain_timer.start(250)
