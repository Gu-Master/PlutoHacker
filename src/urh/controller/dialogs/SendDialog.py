import time

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QIcon, QPen, QCloseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from urh import settings
from urh.controller.dialogs.SendRecvDialog import SendRecvDialog
from urh.dev.VirtualDevice import VirtualDevice, Mode
from urh.signalprocessing.ContinuousNoiseGenerator import ContinuousNoiseGenerator
from urh.signalprocessing.IQArray import IQArray
from urh.signalprocessing.Signal import Signal
from urh.ui.painting.SignalSceneManager import SignalSceneManager
from urh.util import FileOperator
from urh.util.Logger import logger


class SendDialog(SendRecvDialog):
    def __init__(
        self,
        project_manager,
        modulated_data,
        modulation_msg_indices=None,
        continuous_send_mode=False,
        parent=None,
        testing_mode=False,
        embedded=False,
    ):
        super().__init__(
            project_manager,
            is_tx=True,
            continuous_send_mode=continuous_send_mode,
            parent=parent,
            testing_mode=testing_mode,
            embedded=embedded,
        )

        self.graphics_view = self.ui.graphicsViewSend
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_send)
        self.hide_receive_ui_items()

        self.ui.btnStart.setIcon(QIcon.fromTheme("media-playback-start"))
        self.setWindowTitle("Повтор сигнала")
        self.setWindowIcon(QIcon.fromTheme("media-playback-start"))
        self.ui.btnStart.setToolTip("Повторить сигнал")
        self.ui.btnStop.setToolTip("Остановить повтор")
        self.device_is_sending = False
        self.modulation_msg_indices = modulation_msg_indices
        self.noise_generator = None
        self.preview_hint_default_text = self.ui.label_7.text()
        self.default_progress_label_text = self.ui.lSamplesSentText.text()
        self.default_progress_maximum = 0

        if self.modulation_msg_indices is not None:
            self.ui.progressBarMessage.setMaximum(len(self.modulation_msg_indices))
        else:
            self.ui.progressBarMessage.hide()
            self.ui.labelCurrentMessage.hide()

        if modulated_data is not None:
            assert isinstance(modulated_data, IQArray)
            # modulated_data is none in continuous send mode
            self.ui.progressBarSample.setMaximum(len(modulated_data))
            self.default_progress_maximum = len(modulated_data)
            samp_rate = self.device_settings_widget.ui.spinBoxSampleRate.value()
            signal = Signal("", "Modulated Preview", sample_rate=samp_rate)
            signal.iq_array = modulated_data
            self.scene_manager = SignalSceneManager(signal, parent=self)
            self.send_indicator = self.scene_manager.scene.addRect(
                0,
                -2,
                0,
                4,
                QPen(QColor(Qt.GlobalColor.transparent), 0),
                QBrush(settings.SEND_INDICATOR_COLOR),
            )
            self.send_indicator.stackBefore(self.scene_manager.scene.selection_area)
            self.scene_manager.init_scene()
            self.graphics_view.set_signal(signal)
            self.graphics_view.sample_rate = samp_rate

            self.create_connects()
            self.device_settings_widget.update_for_new_device(overwrite_settings=False)

    def create_connects(self):
        super().create_connects()

        self.graphics_view.save_as_clicked.connect(
            self.on_graphics_view_save_as_clicked
        )
        self.scene_manager.signal.data_edited.connect(self.on_signal_data_edited)
        if hasattr(self, "btnCalibrationNoise"):
            self.btnCalibrationNoise.toggled.connect(self.on_calibration_noise_toggled)
            self.sliderNoiseAmplitude.valueChanged.connect(
                self.on_noise_amplitude_value_changed
            )

    @property
    def calibration_noise_enabled(self) -> bool:
        return (
            hasattr(self, "btnCalibrationNoise")
            and self.btnCalibrationNoise.isChecked()
        )

    def _create_calibration_noise_controls(self):
        self.calibrationNoiseFrame = QFrame(self.ui.groupBox)
        self.calibrationNoiseFrame.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self.calibrationNoiseFrame)
        layout.setContentsMargins(8, 8, 8, 8)

        self.btnCalibrationNoise = QPushButton(
            "Включить калибровочный шум", self.calibrationNoiseFrame
        )
        self.btnCalibrationNoise.setCheckable(True)
        self.btnCalibrationNoise.setToolTip(
            "Передавать непрерывный AWGN на выбранной частоте вместо загруженного сигнала"
        )
        layout.addWidget(self.btnCalibrationNoise)

        slider_layout = QHBoxLayout()
        self.labelNoiseAmplitude = QLabel(self.calibrationNoiseFrame)
        slider_layout.addWidget(self.labelNoiseAmplitude)

        self.sliderNoiseAmplitude = QSlider(
            Qt.Orientation.Horizontal, self.calibrationNoiseFrame
        )
        self.sliderNoiseAmplitude.setRange(0, 100)
        self.sliderNoiseAmplitude.setValue(20)
        self.sliderNoiseAmplitude.setToolTip("Амплитуда передаваемого белого шума")
        slider_layout.addWidget(self.sliderNoiseAmplitude, 1)
        layout.addLayout(slider_layout)

        self.labelCalibrationNoiseHint = QLabel(
            "При старте вместо загруженного сигнала будет передаваться непрерывный "
            "шумоподобный I/Q поток на выбранной частоте.",
            self.calibrationNoiseFrame,
        )
        self.labelCalibrationNoiseHint.setWordWrap(True)
        layout.addWidget(self.labelCalibrationNoiseHint)

        self.ui.gridLayout_2.addWidget(self.calibrationNoiseFrame, 3, 0, 1, 2)
        self._update_noise_amplitude_label(self.sliderNoiseAmplitude.value())

    def _update_noise_amplitude_label(self, value: int):
        if hasattr(self, "labelNoiseAmplitude"):
            self.labelNoiseAmplitude.setText(f"Амплитуда шума: {value}%")

    def _rebuild_noise_generator(self):
        if self.device is None:
            return

        amplitude = self.sliderNoiseAmplitude.value() / 100
        if self.noise_generator is not None:
            self.noise_generator.stop()

        self.noise_generator = ContinuousNoiseGenerator(
            dtype=self.device.data_type, amplitude=amplitude
        )

    def _apply_calibration_noise_mode_to_device(self):
        if self.device is None or not hasattr(self, "btnCalibrationNoise"):
            return

        if self.calibration_noise_enabled:
            if self.noise_generator is None:
                self._rebuild_noise_generator()

            self.device.is_send_continuous = True
            self.device.continuous_send_ring_buffer = self.noise_generator.ring_buffer
            self.device.num_samples_to_send = self.noise_generator.nominal_num_samples
            self.device.num_sending_repeats = 0
        else:
            self.device.is_send_continuous = False
            self.device.continuous_send_ring_buffer = None
            self.device.num_samples_to_send = None
            self.device.num_sending_repeats = (
                self.device_settings_widget.ui.spinBoxNRepeat.value()
            )

    def _update_calibration_noise_ui(self):
        if not hasattr(self, "btnCalibrationNoise"):
            return

        if self.calibration_noise_enabled:
            self.btnCalibrationNoise.setText("Выключить калибровочный шум")
            self.ui.label_7.setText(
                "Подсказка: при передаче вместо загруженного сигнала будет отправлен "
                "непрерывный AWGN на выбранной частоте."
            )
        else:
            self.btnCalibrationNoise.setText("Включить калибровочный шум")
            self.ui.label_7.setText(self.preview_hint_default_text)

        self.device_settings_widget.ui.labelNRepeat.setEnabled(
            not self.calibration_noise_enabled
        )
        self.device_settings_widget.ui.spinBoxNRepeat.setEnabled(
            not self.calibration_noise_enabled
        )

        if self.calibration_noise_enabled and self.noise_generator is not None:
            self.ui.lSamplesSentText.setText("Шумовой буфер:")
            self.ui.progressBarSample.setMaximum(
                self.noise_generator.nominal_num_samples
            )
        else:
            self.ui.lSamplesSentText.setText(self.default_progress_label_text)
            self.ui.progressBarSample.setMaximum(self.default_progress_maximum)

    def _wait_for_noise_buffer(self, timeout: float = 1.0) -> bool:
        if self.noise_generator is None:
            return False

        deadline = time.monotonic() + timeout
        target_fill = max(1, self.noise_generator.nominal_num_samples)
        while time.monotonic() < deadline:
            if len(self.noise_generator.ring_buffer) >= target_fill:
                return True
            time.sleep(0.01)

        return len(self.noise_generator.ring_buffer) > 0

    def _update_send_indicator(self, width: int):
        y, h = (
            self.ui.graphicsViewSend.view_rect().y(),
            self.ui.graphicsViewSend.view_rect().height(),
        )
        self.send_indicator.setRect(0, y - h, width, 2 * h + abs(y))

    def set_current_message_progress_bar_value(self, current_sample: int):
        if self.modulation_msg_indices is not None:
            msg_index = next(
                (
                    i
                    for i, sample in enumerate(self.modulation_msg_indices)
                    if sample >= current_sample
                ),
                len(self.modulation_msg_indices),
            )
            self.ui.progressBarMessage.setValue(msg_index + 1)

    def update_view(self):
        if super().update_view():
            self._update_send_indicator(self.device.current_index)
            self.ui.progressBarSample.setValue(self.device.current_index)
            self.set_current_message_progress_bar_value(self.device.current_index)

            if not self.device.sending_finished:
                self.ui.lblCurrentRepeatValue.setText(
                    str(self.device.current_iteration + 1)
                )
            else:
                self.ui.btnStop.click()
                self.ui.lblCurrentRepeatValue.setText("Повтор завершён")

    def init_device(self):
        device_name = self.selected_device_name
        num_repeats = self.device_settings_widget.ui.spinBoxNRepeat.value()
        sts = self.scene_manager.signal.iq_array

        self.device = VirtualDevice(
            self.backend_handler,
            device_name,
            Mode.send,
            samples_to_send=sts,
            device_ip="192.168.10.2",
            sending_repeats=num_repeats,
            parent=self,
        )
        if hasattr(self, "btnCalibrationNoise"):
            self._rebuild_noise_generator()
            self._apply_calibration_noise_mode_to_device()
            self._update_calibration_noise_ui()
        self._create_device_connects()

    @pyqtSlot()
    def on_graphics_view_save_as_clicked(self):
        filename = FileOperator.ask_save_file_name("signal.complex")
        if filename:
            try:
                try:
                    self.scene_manager.signal.sample_rate = self.device.sample_rate
                except Exception as e:
                    logger.exception(e)

                self.scene_manager.signal.save_as(filename)
            except Exception as e:
                QMessageBox.critical(self, self.tr("Error saving signal"), e.args[0])

    @pyqtSlot()
    def on_signal_data_edited(self):
        signal = self.scene_manager.signal
        self.ui.progressBarSample.setMaximum(signal.num_samples)
        self.device.samples_to_send = signal.iq_array.data
        self.scene_manager.init_scene()
        self.ui.graphicsViewSend.redraw_view()

    @pyqtSlot()
    def on_start_clicked(self):
        super().on_start_clicked()
        self._apply_calibration_noise_mode_to_device()

        if (
            not self.calibration_noise_enabled
            and self.ui.progressBarSample.value()
            >= self.ui.progressBarSample.maximum() - 1
        ):
            self.on_clear_clicked()

        if self.calibration_noise_enabled:
            if self.device_is_sending:
                if self.noise_generator is not None:
                    self.noise_generator.stop()
                self.device.stop("Calibration noise paused by user")
            else:
                if self.noise_generator is None:
                    self._rebuild_noise_generator()
                    self._apply_calibration_noise_mode_to_device()

                if not self.noise_generator.is_running:
                    self.noise_generator.start()
                self._wait_for_noise_buffer()
                self.device.start()
        else:
            if self.device_is_sending:
                self.device.stop("Repeating paused by user")
            else:
                self.device.start()

    @pyqtSlot()
    def on_stop_clicked(self):
        if self.noise_generator is not None:
            self.noise_generator.stop()
        super().on_stop_clicked()
        self.on_clear_clicked()

    @pyqtSlot()
    def on_device_stopped(self):
        super().on_device_stopped()
        self.ui.btnStart.setIcon(QIcon.fromTheme("media-playback-start"))
        self.ui.btnStart.setText("Старт")
        self.ui.btnStart.setToolTip("Запустить повтор")
        self.device_is_sending = False
        if hasattr(self, "btnCalibrationNoise"):
            self.btnCalibrationNoise.setEnabled(True)

    @pyqtSlot()
    def on_device_started(self):
        super().on_device_started()
        self.device_is_sending = True
        self.ui.btnStart.setEnabled(True)
        self.ui.btnStart.setIcon(QIcon.fromTheme("media-playback-pause"))
        self.ui.btnStart.setText("Пауза")
        self.set_device_ui_items_enabled(False)
        if hasattr(self, "btnCalibrationNoise"):
            self.btnCalibrationNoise.setEnabled(False)

    @pyqtSlot()
    def on_clear_clicked(self):
        if self.noise_generator is not None:
            self.noise_generator.stop()
        self._apply_calibration_noise_mode_to_device()
        self._update_send_indicator(0)
        self.reset()

    @pyqtSlot(bool)
    def on_calibration_noise_toggled(self, checked: bool):
        if checked and self.noise_generator is None and self.device is not None:
            self._rebuild_noise_generator()

        self._apply_calibration_noise_mode_to_device()
        self._update_calibration_noise_ui()

    @pyqtSlot(int)
    def on_noise_amplitude_value_changed(self, value: int):
        self._update_noise_amplitude_label(value)
        if self.noise_generator is not None:
            self.noise_generator.amplitude = value / 100

    def closeEvent(self, event: QCloseEvent):
        if self.noise_generator is not None:
            self.noise_generator.stop()
        super().closeEvent(event)
