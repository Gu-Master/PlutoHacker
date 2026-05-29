from collections import OrderedDict, namedtuple

DEFAULT_FREQUENCY = 433.92e6
DEFAULT_SAMPLE_RATE = 1e6
DEFAULT_BANDWIDTH = 1e6
DEFAULT_GAIN = 20
DEFAULT_IF_GAIN = 20
DEFAULT_BB_GAIN = 16
DEFAULT_FREQ_CORRECTION = 1
DEFAULT_DIRECT_SAMPLING_MODE = 0

DEVICE_CONFIG = OrderedDict()

dev_range = namedtuple("dev_range", ["start", "stop", "step"])

M = 10**6
G = 10**9

DEVICE_CONFIG["PlutoSDR"] = {
    "center_freq": dev_range(start=70 * M, stop=6 * G, step=1),
    "sample_rate": dev_range(start=2.1 * M, stop=61.44 * M, step=1),
    "bandwidth": dev_range(start=0.2 * M, stop=56 * M, step=1),
    "tx_rf_gain": list(range(-89, 1)),
    "rx_rf_gain": list(range(-3, 72)),
}

DEVICE_CONFIG["Fallback"] = {
    "center_freq": dev_range(start=1 * M, stop=6 * G, step=1),
    "sample_rate": dev_range(start=2 * M, stop=20 * M, step=1),
    "bandwidth": dev_range(start=2 * M, stop=20 * M, step=1),
    "rx_rf_gain": list(range(0, 51)),
    "tx_rf_gain": list(range(0, 51)),
}
