import time
from multiprocessing import Process, Value

import numpy as np

from urh import settings
from urh.signalprocessing.IQArray import IQArray
from urh.util.Logger import logger
from urh.util.RingBuffer import RingBuffer


class ContinuousNoiseGenerator(object):
    """
    Generates complex AWGN samples continuously and stores them in a ring buffer for TX.
    """

    WAIT_TIMEOUT = 0.02
    DEFAULT_CHUNK_SIZE = 16384

    def __init__(self, dtype, amplitude: float = 0.2, chunk_size: int = None):
        self.dtype = np.dtype(dtype)
        self.chunk_size = max(1, chunk_size or self.DEFAULT_CHUNK_SIZE)
        iq_sample_size = 2 * self.dtype.itemsize
        buffer_size = int(settings.CONTINUOUS_BUFFER_SIZE_MB * 1e6) // iq_sample_size
        self.ring_buffer = RingBuffer(max(1, buffer_size), dtype=self.dtype.type)

        self._amplitude = Value("f", 0.0)
        self.amplitude = amplitude

        self.abort = Value("i", 0)
        self.process = Process(target=self.generate_continuously, daemon=True)

    @property
    def amplitude(self) -> float:
        return float(self._amplitude.value)

    @amplitude.setter
    def amplitude(self, value: float):
        self._amplitude.value = max(0.0, min(1.0, float(value)))

    @property
    def is_running(self) -> bool:
        return self.process.is_alive()

    @property
    def nominal_num_samples(self) -> int:
        return min(self.chunk_size, self.ring_buffer.size)

    def start(self):
        self.abort.value = 0
        try:
            self.process = Process(target=self.generate_continuously, daemon=True)
            self.process.start()
        except RuntimeError as e:
            logger.exception(e)

    def stop(self, clear_buffer=True):
        self.abort.value = 1

        if self.process.is_alive():
            try:
                self.process.join(1.5)
            except RuntimeError as e:
                logger.exception(e)
            if self.process.is_alive():
                self.process.terminate()

        if clear_buffer:
            self.ring_buffer.clear()

        logger.debug("Stopped continuous AWGN generation")

    def generate_continuously(self):
        rng = np.random.default_rng()
        min_val, max_val = IQArray.min_max_for_dtype(self.dtype.type)
        peak = float(abs(max_val))
        target_chunk_size = min(self.chunk_size, self.ring_buffer.size)

        while not self.abort.value:
            space_left = self.ring_buffer.space_left
            if space_left <= 0:
                time.sleep(self.WAIT_TIMEOUT)
                continue

            n_samples = min(target_chunk_size, space_left)
            amplitude = self.amplitude

            if amplitude <= 0:
                noise = np.zeros((n_samples, 2), dtype=self.dtype)
            else:
                sigma = amplitude * peak / 3.0
                noise = rng.normal(0.0, sigma, size=(n_samples, 2))
                np.clip(noise, min_val, max_val, out=noise)
                noise = noise.astype(self.dtype, copy=False)

            self.ring_buffer.push(noise)
