import time
from enum import Enum

import numpy as np
from PyQt6.QtCore import pyqtSignal, QObject

from urh.dev import config
from urh.dev.BackendHandler import Backends, BackendHandler
from urh.dev.native.Device import Device
from urh.util.Logger import logger


class Mode(Enum):
    receive = 1
    send = 2
    spectrum = 3


class VirtualDevice(QObject):
    """
    Wrapper for the PlutoSDR native device backend.
    """

    started = pyqtSignal()
    stopped = pyqtSignal()
    sender_needs_restart = pyqtSignal()

    fatal_error_occurred = pyqtSignal(str)
    ready_for_action = pyqtSignal()

    continuous_send_msg = "Continuous send mode requires the PlutoSDR native backend."

    def __init__(
        self,
        backend_handler,
        name: str,
        mode: Mode,
        freq=None,
        sample_rate=None,
        bandwidth=None,
        gain=None,
        if_gain=None,
        baseband_gain=None,
        samples_to_send=None,
        device_ip=None,
        sending_repeats=1,
        parent=None,
        resume_on_full_receive_buffer=False,
        raw_mode=True,
        portnumber=1234,
    ):
        super().__init__(parent)
        self.name = name
        self.mode = mode
        self.backend_handler = backend_handler
        self.__data_timestamp = 0

        freq = config.DEFAULT_FREQUENCY if freq is None else freq
        sample_rate = config.DEFAULT_SAMPLE_RATE if sample_rate is None else sample_rate
        bandwidth = config.DEFAULT_BANDWIDTH if bandwidth is None else bandwidth
        gain = config.DEFAULT_GAIN if gain is None else gain
        if_gain = config.DEFAULT_IF_GAIN if if_gain is None else if_gain
        baseband_gain = (
            config.DEFAULT_BB_GAIN if baseband_gain is None else baseband_gain
        )

        resume_on_full_receive_buffer = (
            self.mode == Mode.spectrum or resume_on_full_receive_buffer
        )

        try:
            self.backend = self.backend_handler.device_backends[
                name.lower()
            ].selected_backend
        except KeyError:
            logger.warning("Invalid device name: {0}".format(name))
            self.backend = Backends.none
            self.__dev = None
            return

        if self.backend == Backends.native:
            name = self.name.lower()
            if name in map(str.lower, BackendHandler.DEVICE_NAMES):
                if name == "plutosdr":
                    from urh.dev.native.PlutoSDR import PlutoSDR

                    self.__dev = PlutoSDR(
                        center_freq=freq,
                        sample_rate=sample_rate,
                        bandwidth=bandwidth,
                        gain=gain,
                        resume_on_full_receive_buffer=resume_on_full_receive_buffer,
                    )
                else:
                    raise NotImplementedError(
                        "Only PlutoSDR native backend is supported"
                    )

            elif name == "test":
                # Internal dummy device path.
                self.__dev = Device(
                    freq,
                    sample_rate,
                    bandwidth,
                    gain,
                    if_gain,
                    baseband_gain,
                    resume_on_full_receive_buffer,
                )
            else:
                raise ValueError("Unknown device name {0}".format(name))
            self.__dev.portnumber = portnumber
            self.__dev.device_ip = device_ip
            if mode == Mode.send:
                self.__dev.init_send_parameters(samples_to_send, sending_repeats)
        elif self.backend == Backends.none:
            self.__dev = None
        else:
            raise ValueError("Unsupported Backend")

        if mode == Mode.spectrum:
            self.__dev.is_in_spectrum_mode = True

    @property
    def backend_is_native(self) -> bool:
        return self.backend == Backends.native

    @property
    def data_type(self):
        if self.backend == Backends.native:
            return self.__dev.DATA_TYPE
        else:
            return np.float32

    @property
    def has_multi_device_support(self):
        return (
            hasattr(self.__dev, "has_multi_device_support")
            and self.__dev.has_multi_device_support
        )

    @property
    def device_serial(self):
        if hasattr(self.__dev, "device_serial"):
            return self.__dev.device_serial
        else:
            return None

    @device_serial.setter
    def device_serial(self, value):
        if hasattr(self.__dev, "device_serial"):
            self.__dev.device_serial = value

    @property
    def device_number(self):
        if hasattr(self.__dev, "device_number"):
            return self.__dev.device_number
        else:
            return None

    @device_number.setter
    def device_number(self, value):
        if hasattr(self.__dev, "device_number"):
            self.__dev.device_number = value

    @property
    def bandwidth(self):
        return self.__dev.bandwidth

    @bandwidth.setter
    def bandwidth(self, value):
        self.__dev.bandwidth = value

    @property
    def apply_dc_correction(self):
        if self.backend == Backends.native:
            return self.__dev.apply_dc_correction
        else:
            return None

    @apply_dc_correction.setter
    def apply_dc_correction(self, value: bool):
        if self.backend == Backends.native:
            self.__dev.apply_dc_correction = bool(value)

    @property
    def bias_tee_enabled(self):
        if self.backend_is_native:
            return self.__dev.bias_tee_enabled
        else:
            return None

    @bias_tee_enabled.setter
    def bias_tee_enabled(self, value: bool):
        if self.backend_is_native:
            self.__dev.bias_tee_enabled = value

    @property
    def bandwidth_is_adjustable(self):
        if self.backend == Backends.native:
            return self.__dev.bandwidth_is_adjustable
        else:
            raise ValueError("Unsupported Backend")

    @property
    def frequency(self):
        if self.backend == Backends.native:
            return self.__dev.frequency
        else:
            raise ValueError("Unsupported Backend")

    @frequency.setter
    def frequency(self, value):
        if self.backend == Backends.native:
            self.__dev.frequency = value
        else:
            raise ValueError("Unsupported Backend")

    @property
    def num_samples_to_send(self) -> int:
        if self.backend == Backends.native:
            return self.__dev.num_samples_to_send
        else:
            raise ValueError(self.continuous_send_msg)

    @num_samples_to_send.setter
    def num_samples_to_send(self, value: int):
        if self.backend == Backends.native:
            self.__dev.num_samples_to_send = value
        else:
            raise ValueError(self.continuous_send_msg)

    @property
    def is_send_continuous(self) -> bool:
        if self.backend == Backends.native:
            return self.__dev.sending_is_continuous
        else:
            raise ValueError(self.continuous_send_msg)

    @is_send_continuous.setter
    def is_send_continuous(self, value: bool):
        if self.backend == Backends.native:
            self.__dev.sending_is_continuous = value
        else:
            raise ValueError(self.continuous_send_msg)

    @property
    def is_raw_mode(self) -> bool:
        return True

    @property
    def continuous_send_ring_buffer(self):
        if self.backend == Backends.native:
            return self.__dev.continuous_send_ring_buffer
        else:
            raise ValueError(self.continuous_send_msg)

    @continuous_send_ring_buffer.setter
    def continuous_send_ring_buffer(self, value):
        if self.backend == Backends.native:
            self.__dev.continuous_send_ring_buffer = value
        else:
            raise ValueError(self.continuous_send_msg)

    @property
    def is_in_spectrum_mode(self):
        if self.backend == Backends.native:
            return self.__dev.is_in_spectrum_mode
        else:
            raise ValueError("Unsupported Backend")

    @is_in_spectrum_mode.setter
    def is_in_spectrum_mode(self, value: bool):
        if self.backend == Backends.native:
            self.__dev.is_in_spectrum_mode = value
        else:
            raise ValueError("Unsupported Backend")

    @property
    def gain(self):
        return self.__dev.gain

    @gain.setter
    def gain(self, value):
        try:
            self.__dev.gain = value
        except AttributeError as e:
            logger.warning(str(e))

    @property
    def if_gain(self):
        try:
            return self.__dev.if_gain
        except AttributeError as e:
            logger.warning(str(e))

    @if_gain.setter
    def if_gain(self, value):
        try:
            self.__dev.if_gain = value
        except AttributeError as e:
            logger.warning(str(e))

    @property
    def baseband_gain(self):
        return self.__dev.baseband_gain

    @baseband_gain.setter
    def baseband_gain(self, value):
        self.__dev.baseband_gain = value

    @property
    def sample_rate(self):
        try:
            return self.__dev.sample_rate
        except:
            return 1e6

    @sample_rate.setter
    def sample_rate(self, value):
        self.__dev.sample_rate = value

    @property
    def channel_index(self) -> int:
        return self.__dev.channel_index

    @channel_index.setter
    def channel_index(self, value: int):
        self.__dev.channel_index = value

    @property
    def antenna_index(self) -> int:
        return self.__dev.antenna_index

    @antenna_index.setter
    def antenna_index(self, value: int):
        self.__dev.antenna_index = value

    @property
    def freq_correction(self):
        return self.__dev.freq_correction

    @freq_correction.setter
    def freq_correction(self, value):
        self.__dev.freq_correction = value

    @property
    def direct_sampling_mode(self) -> int:
        return self.__dev.direct_sampling_mode

    @direct_sampling_mode.setter
    def direct_sampling_mode(self, value):
        self.__dev.direct_sampling_mode = value

    @property
    def samples_to_send(self):
        if self.backend == Backends.native:
            return self.__dev.samples_to_send
        else:
            raise ValueError("Unsupported Backend")

    @samples_to_send.setter
    def samples_to_send(self, value):
        if self.backend == Backends.native:
            self.__dev.init_send_parameters(value, self.num_sending_repeats)
        else:
            raise ValueError("Unsupported Backend")

    @property
    def subdevice(self):
        if hasattr(self.__dev, "subdevice"):
            return self.__dev.subdevice
        else:
            return None

    @subdevice.setter
    def subdevice(self, value: str):
        if hasattr(self.__dev, "subdevice"):
            self.__dev.subdevice = value

    @property
    def ip(self):
        if self.backend == Backends.native:
            return self.__dev.device_ip
        else:
            raise ValueError("Unsupported Backend")

    @ip.setter
    def ip(self, value):
        if self.backend == Backends.native:
            self.__dev.device_ip = value
        elif self.backend == Backends.none:
            return
        else:
            raise ValueError("Unsupported Backend")

    @property
    def port(self):
        if self.backend == Backends.native:
            return self.__dev.port
        else:
            raise ValueError("Unsupported Backend")

    @port.setter
    def port(self, value):
        if self.backend == Backends.native:
            self.__dev.port = value
        else:
            raise ValueError("Unsupported Backend")

    @property
    def data(self):
        if self.backend == Backends.native:
            if self.mode == Mode.send:
                return self.__dev.samples_to_send
            else:
                return self.__dev.receive_buffer
        else:
            raise ValueError("Unsupported Backend")

    @data.setter
    def data(self, value):
        if self.backend == Backends.native:
            if self.mode == Mode.send:
                self.__dev.samples_to_send = value
            else:
                self.__dev.receive_buffer = value
        else:
            logger.warning(
                "{}:{} has no data".format(self.__class__.__name__, self.backend.name)
            )

    @property
    def data_timestamp(self):
        if self.backend == Backends.native:
            try:
                self.__data_timestamp = (
                    self.__dev.first_data_timestamp
                )  # more accurate timestamp
            except:
                pass
        return self.__data_timestamp

    def reset_data_timestamp(self):
        if self.backend == Backends.native:
            self.__dev.reset_first_data_timestamp()
        else:
            self.__data_timestamp = time.time()

    def free_data(self):
        if self.backend == Backends.native:
            self.__dev.samples_to_send = None
            self.__dev.receive_buffer = None
        elif self.backend == Backends.none:
            pass
        else:
            raise ValueError("Unsupported Backend")

    @property
    def resume_on_full_receive_buffer(self) -> bool:
        return self.__dev.resume_on_full_receive_buffer

    @resume_on_full_receive_buffer.setter
    def resume_on_full_receive_buffer(self, value: bool):
        if value != self.__dev.resume_on_full_receive_buffer:
            self.__dev.resume_on_full_receive_buffer = value
            if self.backend == Backends.native:
                self.__dev.receive_buffer = None

    @property
    def num_sending_repeats(self):
        return self.__dev.sending_repeats

    @num_sending_repeats.setter
    def num_sending_repeats(self, value):
        self.__dev.sending_repeats = value

    @property
    def current_index(self):
        if self.backend == Backends.native:
            if self.mode == Mode.send:
                return self.__dev.current_sent_sample
            else:
                return self.__dev.current_recv_index
        else:
            raise ValueError("Unsupported Backend")

    @current_index.setter
    def current_index(self, value):
        if self.backend == Backends.native:
            if self.mode == Mode.send:
                self.__dev.current_sent_sample = value
            else:
                self.__dev.current_recv_index = value
        else:
            raise ValueError("Unsupported Backend")

    @property
    def current_iteration(self):
        if self.backend == Backends.native:
            return self.__dev.current_sending_repeat
        else:
            raise ValueError("Unsupported Backend")

    @current_iteration.setter
    def current_iteration(self, value):
        if self.backend == Backends.native:
            self.__dev.current_sending_repeat = value
        else:
            raise ValueError("Unsupported Backend")

    @property
    def sending_finished(self):
        if self.backend == Backends.native:
            return self.__dev.sending_finished
        else:
            raise ValueError("Unsupported Backend")

    @property
    def spectrum(self):
        if self.mode == Mode.spectrum:
            if self.backend == Backends.native:
                w = np.abs(np.fft.fft(self.__dev.receive_buffer.as_complex64()))
                freqs = np.fft.fftfreq(len(w), 1 / self.sample_rate)
                idx = np.argsort(freqs)
                return freqs[idx].astype(np.float32), w[idx].astype(np.float32)
        else:
            raise ValueError("Spectrum x only available in spectrum mode")

    def start(self):
        self.__data_timestamp = time.time()
        if self.backend == Backends.native:
            if self.mode == Mode.send:
                self.__dev.start_tx_mode(resume=True)
            else:
                self.__dev.start_rx_mode()

            self.emit_started_signal()
        else:
            raise ValueError("Unsupported Backend")

    def stop(self, msg: str):
        if self.backend == Backends.native:
            if self.mode == Mode.send:
                self.__dev.stop_tx_mode(msg)
            else:
                self.__dev.stop_rx_mode(msg)
            self.emit_stopped_signal()
        elif self.backend == Backends.none:
            pass
        else:
            logger.error("Stop device: Unsupported backend " + str(self.backend))

    def stop_on_error(self, msg: str):
        if self.backend == Backends.native:
            self.read_messages()  # Clear errors
            self.__dev.stop_rx_mode("Stop on error")
            self.__dev.stop_tx_mode("Stop on error")
            self.emit_stopped_signal()
        else:
            raise ValueError("Unsupported Backend")

    def cleanup(self):
        if self.backend == Backends.native:
            self.data = None

        elif self.backend == Backends.none:
            pass

        else:
            raise ValueError("Unsupported Backend")

    def emit_stopped_signal(self):
        self.stopped.emit()

    def emit_started_signal(self):
        self.started.emit()

    def emit_sender_needs_restart(self):
        self.sender_needs_restart.emit()

    def read_messages(self) -> str:
        """
        returns a string of new device messages separated by newlines

        :return:
        """
        if self.backend == Backends.native:
            messages = "\n".join(self.__dev.device_messages)
            self.__dev.device_messages.clear()

            if messages and not messages.endswith("\n"):
                messages += "\n"

            if "successfully started" in messages:
                self.ready_for_action.emit()
            elif "failed to start" in messages:
                self.fatal_error_occurred.emit(
                    messages[messages.index("failed to start") :]
                )

            return messages
        else:
            raise ValueError("Unsupported Backend")

    def set_server_port(self, port: int):
        raise ValueError("Network backend is not supported in this PlutoSDR build")

    def set_client_port(self, port: int):
        raise ValueError("Network backend is not supported in this PlutoSDR build")

    def get_device_list(self):
        if hasattr(self.__dev, "get_device_list"):
            return self.__dev.get_device_list()
        else:
            return []

    def increase_gr_port(self):
        raise ValueError("Only the native PlutoSDR backend is supported")

    def emit_ready_for_action(self):
        """
        Notify observers that device is successfully initialized
        :return:
        """
        self.ready_for_action.emit()

    def emit_fatal_error_occurred(self, msg: str):
        self.fatal_error_occurred.emit(msg)
