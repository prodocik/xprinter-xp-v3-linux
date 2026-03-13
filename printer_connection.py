"""Printer connection manager — Bluetooth, USB, and WiFi."""

import glob
import socket
import threading
from abc import ABC, abstractmethod


class PrinterConnection(ABC):
    """Abstract base for printer connections."""

    @abstractmethod
    def connect(self):
        """Establish connection. Raises on failure."""

    @abstractmethod
    def send(self, data: bytes):
        """Send raw bytes to printer."""

    @abstractmethod
    def disconnect(self):
        """Close connection."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable connection description."""


class USBConnection(PrinterConnection):
    """Connect via USB serial port (/dev/ttyUSB* or /dev/usb/lp*)."""

    def __init__(self, port=None, baudrate=9600):
        self._port = port
        self._baudrate = baudrate
        self._serial = None

    @staticmethod
    def find_ports():
        """Find available USB printer ports."""
        ports = []
        # Serial ports
        ports.extend(glob.glob("/dev/ttyUSB*"))
        ports.extend(glob.glob("/dev/ttyACM*"))
        # Direct USB printer ports
        ports.extend(glob.glob("/dev/usb/lp*"))
        return sorted(ports)

    @property
    def port(self):
        return self._port

    @port.setter
    def port(self, value):
        self._port = value

    def connect(self):
        import serial
        if not self._port:
            ports = self.find_ports()
            if not ports:
                raise ConnectionError("USB-принтер не найден")
            self._port = ports[0]

        self._serial = serial.Serial(
            self._port,
            baudrate=self._baudrate,
            timeout=5,
            write_timeout=10,
        )

    def send(self, data: bytes):
        if not self._serial or not self._serial.is_open:
            raise ConnectionError("USB не подключён")
        self._serial.write(data)
        self._serial.flush()

    def disconnect(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def display_name(self):
        return f"USB: {self._port or 'не выбран'}"


class BluetoothConnection(PrinterConnection):
    """Connect via Bluetooth RFCOMM."""

    def __init__(self, address=None, channel=1):
        self._address = address
        self._channel = channel
        self._sock = None

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, value):
        self._address = value

    @staticmethod
    def scan_devices():
        """Scan for nearby Bluetooth devices. Returns list of (address, name)."""
        try:
            import bluetooth
            devices = bluetooth.discover_devices(
                duration=8, lookup_names=True, lookup_class=False
            )
            return devices
        except ImportError:
            # Fallback: use bluetoothctl via subprocess
            import subprocess
            result = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True, text=True, timeout=10,
            )
            devices = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    devices.append((parts[1], parts[2]))
            return devices

    def connect(self):
        if not self._address:
            raise ConnectionError("Bluetooth адрес не указан")
        self._sock = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
        )
        self._sock.settimeout(10)
        self._sock.connect((self._address, self._channel))

    def send(self, data: bytes):
        if not self._sock:
            raise ConnectionError("Bluetooth не подключён")
        self._sock.sendall(data)

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def is_connected(self) -> bool:
        if not self._sock:
            return False
        try:
            self._sock.getpeername()
            return True
        except OSError:
            return False

    @property
    def display_name(self):
        return f"Bluetooth: {self._address or 'не выбран'}"


class WiFiConnection(PrinterConnection):
    """Connect via TCP to printer's IP on port 9100."""

    def __init__(self, host=None, port=9100):
        self._host = host
        self._port = port
        self._sock = None

    @property
    def host(self):
        return self._host

    @host.setter
    def host(self, value):
        self._host = value

    def connect(self):
        if not self._host:
            raise ConnectionError("IP адрес не указан")
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(10)
        self._sock.connect((self._host, self._port))

    def send(self, data: bytes):
        if not self._sock:
            raise ConnectionError("WiFi не подключён")
        self._sock.sendall(data)

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def is_connected(self) -> bool:
        if not self._sock:
            return False
        try:
            self._sock.getpeername()
            return True
        except OSError:
            return False

    @property
    def display_name(self):
        return f"WiFi: {self._host or 'не выбран'}:{self._port}"


class ConnectionManager:
    """Manages the active printer connection."""

    CONNECTION_TYPES = {
        "USB": USBConnection,
        "Bluetooth": BluetoothConnection,
        "WiFi": WiFiConnection,
    }

    def __init__(self):
        self._connection = None
        self._lock = threading.Lock()

    @property
    def connection(self):
        return self._connection

    def create_connection(self, conn_type, **kwargs):
        """Create a new connection of the specified type."""
        self.disconnect()
        cls = self.CONNECTION_TYPES[conn_type]
        self._connection = cls(**kwargs)
        return self._connection

    def connect(self):
        if not self._connection:
            raise ConnectionError("Соединение не настроено")
        with self._lock:
            self._connection.connect()

    def send(self, data: bytes):
        if not self._connection:
            raise ConnectionError("Соединение не настроено")
        with self._lock:
            self._connection.send(data)

    def disconnect(self):
        if self._connection:
            with self._lock:
                self._connection.disconnect()

    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected()
