from enum import Enum

from urh import settings


class Backends(Enum):
    none = "no available backend"
    native = "native backend"


class BackendContainer(object):
    def __init__(self, name, avail_backends: set, supports_rx: bool, supports_tx: bool):
        self.name = name
        self.avail_backends = avail_backends
        backend_name = settings.read(name + "_selected_backend", "native")
        self.selected_backend = Backends.__members__.get(backend_name, Backends.none)
        if self.selected_backend not in self.avail_backends:
            self.selected_backend = Backends.none

        if self.selected_backend == Backends.none:
            if Backends.native in self.avail_backends:
                self.selected_backend = Backends.native

        self.is_enabled = settings.read(name + "_is_enabled", True, bool)
        self.__supports_rx = supports_rx
        self.__supports_tx = supports_tx
        if len(self.avail_backends) == 0:
            self.is_enabled = False

    def __repr__(self):
        return (
            "avail backends: "
            + str(self.avail_backends)
            + "| selected backend:"
            + str(self.selected_backend)
        )

    @property
    def supports_rx(self) -> bool:
        return self.__supports_rx

    @property
    def supports_tx(self) -> bool:
        return self.__supports_tx

    @property
    def has_native_backend(self):
        return Backends.native in self.avail_backends

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        self.write_settings()

    def set_selected_backend(self, sel_backend: Backends):
        self.selected_backend = sel_backend
        self.write_settings()

    def write_settings(self):
        settings.write(self.name + "_is_enabled", self.is_enabled)
        settings.write(self.name + "_selected_backend", self.selected_backend.name)


class BackendHandler(object):
    """
    This class controls the devices backend.
    1) List available backends for devices
    2) List available devices (at least one backend)
    3) Manage the selection of devices backend

    """

    DEVICE_NAMES = ("PlutoSDR",)

    def __init__(self):
        self.native_backend_only = True
        self.device_backends = {}
        """:type: dict[str, BackendContainer] """

        self.get_backends()

    @property
    def gr_python_interpreter(self):
        return ""

    @gr_python_interpreter.setter
    def gr_python_interpreter(self, value):
        settings.write("gr_python_interpreter", "")

    @property
    def num_native_backends(self):
        return len(
            [
                dev
                for dev, backend_container in self.device_backends.items()
                if Backends.native in backend_container.avail_backends
                and dev.lower() != "rtl-tcp"
            ]
        )

    @property
    def __plutosdr_native_enabled(self) -> bool:
        try:
            from urh.dev.native.lib import plutosdr

            return True
        except ImportError:
            return False

    def set_native_backend_status(self, force=False):
        self.native_backend_only = True

    def __avail_backends_for_device(self, devname: str):
        backends = set()
        supports_rx, supports_tx = False, False

        if devname.lower() != "plutosdr":
            return backends, supports_rx, supports_tx

        if devname.lower() == "plutosdr" and self.__plutosdr_native_enabled:
            supports_rx, supports_tx = True, True
            backends.add(Backends.native)

        return backends, supports_rx, supports_tx

    def get_backends(self):
        self.device_backends.clear()
        for device_name in self.DEVICE_NAMES:
            ab, rx_suprt, tx_suprt = self.__avail_backends_for_device(device_name)
            container = BackendContainer(device_name.lower(), ab, rx_suprt, tx_suprt)
            self.device_backends[device_name.lower()] = container

    def get_key_from_device_display_text(self, displayed_device_name):
        displayed_device_name = displayed_device_name.lower()
        for key in self.DEVICE_NAMES:
            key = key.lower()
            if displayed_device_name.startswith(key):
                return key
        return None
