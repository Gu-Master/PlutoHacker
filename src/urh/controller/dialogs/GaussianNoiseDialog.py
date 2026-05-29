import time

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from urh.controller.dialogs.SendRecvDialog import SendRecvDialog
from urh.dev.VirtualDevice import VirtualDevice, Mode
from urh.signalprocessing.ContinuousNoiseGenerator import ContinuousNoiseGenerator
from urh.ui.painting.ContinuousSceneManager import ContinuousSceneManager


class GaussianNoiseDialog(SendRecvDialog):
    def __init__(self, project_manager, parent=None, testing_mode=False, embedded=False):
        super().__init__(
            project_manager,
            is_tx=True,
            continuous_send_mode=True,
            parent=parent,
            testing_mode=testing_mode,
            embedded=embedded,
        )

        self.graphics_view = self.ui.graphicsViewContinuousSend
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_continuous_send)
        self.hide_receive_ui_items()
        self.ui.progressBarMessage.hide()
        self.ui.labelCurrentMessage.hide()
        self.ui.btnSave.hide()

        self.setWindowTitle("Гауссовский шум")
        self.setWindowIcon(QIcon.fromTheme("media-playback-start"))
        self.ui.btnStart.setIcon(QIcon.fromTheme("media-playback-start"))
        self.ui.btnStart.setToolTip("Запустить передачу шума")
        self.ui.btnStop.setToolTip("Остановить передачу шума")
        self.ui.lSamplesSentText.setText("Заполнение буфера:")
        self.ui.lblRepeatText.setText("Состояние:")
        self.ui.lblCurrentRepeatValue.setText("Ожидание")

        self.device_is_sending = False
        self.noise_generator = None
        self.scene_manager = None

        self._create_noise_controls()
        self.create_connects()
        self.device_settings_widget.update_for_new_device(overwrite_settings=False)

    def _create_noise_controls(self):
        self.noiseControlFrame = QFrame(self.ui.groupBox)
        self.noiseControlFrame.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self.noiseControlFrame)
        layout.setContentsMargins(8, 8, 8, 8)

        self.labelNoiseTitle = QLabel(
            "Тип сигнала: аддитивный белый гауссовский шум (AWGN)",
            self.noiseControlFrame,
        )
        self.labelNoiseTitle.setWordWrap(True)
        layout.addWidget(self.labelNoiseTitle)

        slider_layout = QHBoxLayout()
        self.labelNoiseAmplitude = QLabel(self.noiseControlFrame)
        slider_layout.addWidget(self.labelNoiseAmplitude)

        self.sliderNoiseAmplitude = QSlider(
            Qt.Orientation.Horizontal, self.noiseControlFrame
        )
        self.sliderNoiseAmplitude.setRange(0, 100)
        self.sliderNoiseAmplitude.setValue(20)
        self.sliderNoiseAmplitude.setToolTip("Амплитуда передаваемого белого шума")
        slider_layout.addWidget(self.sliderNoiseAmplitude, 1)
        layout.addLayout(slider_layout)

        self.labelNoiseHint = QLabel(
            "Вкладка передает непрерывный тестовый шумоподобный сигнал на выбранной "
            "частоте и может использоваться для калибровки водопада и оценки "
            "динамического диапазона приемника.",
            self.noiseControlFrame,
        )
        self.labelNoiseHint.setWordWrap(True)
        layout.addWidget(self.labelNoiseHint)

        self.ui.gridLayout_2.addWidget(self.noiseControlFrame, 3, 0, 1, 2)
        self._update_noise_amplitude_label(self.sliderNoiseAmplitude.value())

    def create_connects(self):
        super().create_connects()
        self.sliderNoiseAmplitude.valueChanged.connect(
            self.on_noise_amplitude_value_changed
        )

    def _update_noise_amplitude_label(self, value: int):
        self.labelNoiseAmplitude.setText(f"Амплитуда шума: {value}%")

    def _stop_noise_generator(self, clear_buffer=True):
        if self.noise_generator is not None:
            self.noise_generator.stop(clear_buffer=clear_buffer)

    def _rebuild_noise_generator(self):
        if self.device is None:
            return

        self._stop_noise_generator()
        self.noise_generator = ContinuousNoiseGenerator(
            dtype=self.device.data_type,
            amplitude=self.sliderNoiseAmplitude.value() / 100,
        )

    def _configure_device_for_noise(self):
        if self.device is None or self.noise_generator is None:
            return

        self.device.is_send_continuous = True
        self.device.continuous_send_ring_buffer = self.noise_generator.ring_buffer
        self.device.num_samples_to_send = self.noise_generator.nominal_num_samples
        self.device.num_sending_repeats = 0

        self.ui.progressBarSample.setMaximum(self.noise_generator.nominal_num_samples)

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

    def _refresh_status_labels(self):
        if self.device_is_sending:
            self.ui.lblCurrentRepeatValue.setText("Передача")
        else:
            self.ui.lblCurrentRepeatValue.setText("Ожидание")

    def init_device(self):
        device_name = self.selected_device_name
        self._stop_noise_generator()

        self.device = VirtualDevice(
            self.backend_handler,
            device_name,
            Mode.send,
            device_ip="192.168.10.2",
            sending_repeats=0,
            parent=self,
        )
        self.ui.btnStart.setEnabled(True)

        self._rebuild_noise_generator()
        self._configure_device_for_noise()
        self._create_device_connects()

        if self.scene_manager is None:
            self.scene_manager = ContinuousSceneManager(
                ring_buffer=self.noise_generator.ring_buffer, parent=self
            )
            self.graphics_view.setScene(self.scene_manager.scene)
            self.graphics_view.scene_manager = self.scene_manager
        else:
            self.scene_manager.ring_buffer = self.noise_generator.ring_buffer

        self.scene_manager.init_scene()
        self.scene_manager.clear_path()
        self.graphics_view.update()
        self._refresh_status_labels()

    def update_view(self):
        super().update_view()

        if self.noise_generator is not None:
            current_fill = min(
                len(self.noise_generator.ring_buffer),
                self.noise_generator.nominal_num_samples,
            )
            self.ui.progressBarSample.setValue(current_fill)

        if self.scene_manager is not None:
            self.scene_manager.init_scene()
            self.scene_manager.show_full_scene()
            self.graphics_view.update()

    @pyqtSlot()
    def on_start_clicked(self):
        super().on_start_clicked()

        if self.noise_generator is None:
            self._rebuild_noise_generator()
            self._configure_device_for_noise()

        if not self.noise_generator.is_running:
            self.noise_generator.start()

        self._wait_for_noise_buffer()
        self.device.start()

    @pyqtSlot()
    def on_stop_clicked(self):
        self._stop_noise_generator(clear_buffer=False)
        self.device.stop("Stopped sending Gaussian noise")

    @pyqtSlot()
    def on_clear_clicked(self):
        if self.device_is_sending:
            self.device.stop("Gaussian noise cleared by user")
            return

        self._stop_noise_generator()
        if self.scene_manager is not None:
            self.scene_manager.clear_path()
        self.reset()
        self.ui.progressBarSample.setValue(0)
        self._refresh_status_labels()

    @pyqtSlot()
    def on_device_started(self):
        super().on_device_started()
        self.device_is_sending = True
        self.set_device_ui_items_enabled(False)
        self._refresh_status_labels()

    @pyqtSlot()
    def on_device_stopped(self):
        super().on_device_stopped()
        self.device_is_sending = False
        self._stop_noise_generator(clear_buffer=False)
        self._refresh_status_labels()

    @pyqtSlot(int)
    def on_noise_amplitude_value_changed(self, value: int):
        self._update_noise_amplitude_label(value)
        if self.noise_generator is not None:
            self.noise_generator.amplitude = value / 100
