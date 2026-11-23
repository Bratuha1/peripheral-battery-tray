"""Battery readers for USB receivers and the standard BLE Battery Service."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re
from time import monotonic
import tomllib
from typing import Callable
from uuid import NAMESPACE_URL, UUID, uuid5

import hid
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError


BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
BLE_ERRORS = (BleakError, OSError)
LOGITECH_QUERY = bytes.fromhex("51 08 00 03 1a 00 03 00 04 0a")
LOGITECH_OFFLINE = bytes.fromhex("51 05 00 ff 03 1a 0b 00")
IPI_QUERY = bytes.fromhex("08 02 00 00 00 f5")
BLUETOOTH_ADDRESS = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", re.ASCII)


@dataclass(frozen=True)
class Device:
    name: str
    kind: str
    icon_id: UUID
    read: Callable[[], int | None]


@dataclass(frozen=True)
class UsbProfile:
    name: str
    kind: str
    icon_id: UUID
    vendor_id: int
    product_id: int
    usage_page: int
    usage: int
    read: Callable[[tuple[bytes, ...]], int | None]

    def find(self, interfaces):
        paths = tuple(i["path"] for i in interfaces if (
            i["vendor_id"], i["product_id"], i["usage_page"], i["usage"]
        ) == (self.vendor_id, self.product_id, self.usage_page, self.usage))
        if not paths:
            return None
        return Device(self.name, self.kind, self.icon_id, lambda: self.read(paths))


def ipi_level(report):
    if len(report) < 10 or report[:5] != b"\x08\x02\x00\x00\x04":
        return None
    if sum(report[:10]) % 256 != 255 or report[6] == 0:
        return None
    level = report[7] & 127
    # The IPI web driver treats zero in this status reply as a loading value.
    return level if 0 < level <= 100 else None


def logitech_level(report):
    if len(report) >= 13 and report[:2] == b"\x51\x0b" and report[8] == 4:
        return report[10] if report[10] <= 100 else None
    return None


def query_hid(device, request, parse, offline=b""):
    if device.write(request.ljust(64, b"\0")) != 64:
        return None
    deadline = monotonic() + 1
    while monotonic() < deadline:
        report = bytes(device.read(64, 100))
        if offline and report.startswith(offline):
            return None
        level = parse(report)
        if level is not None:
            return level
    return None


def read_ipi(paths):
    for path in paths:
        device = hid.device()
        try:
            device.open_path(path)
            # The receiver has two collections with the same usage. Select
            # numbered report 8 with 63-byte input and output payloads.
            descriptor = bytes(device.get_report_descriptor())
            if b"\x85\x08" not in descriptor or b"\x95\x3f\x91" not in descriptor:
                continue
            return query_hid(device, IPI_QUERY, ipi_level)
        except OSError:
            continue
        finally:
            device.close()
    return None


def read_logitech(paths):
    device = hid.device()
    try:
        device.open_path(paths[0])
        return query_hid(device, LOGITECH_QUERY, logitech_level, LOGITECH_OFFLINE)
    except OSError:
        return None
    finally:
        device.close()


USB_PROFILES = (
    UsbProfile("IPI Haze X Pro", "mouse", UUID("47b3ec39-8bfb-4cc5-bb98-8d92e589df43"),
               0x372E, 0x10F9, 0xFF04, 0x0001, read_ipi),
    UsbProfile("Logitech PRO X 2 LIGHTSPEED", "headset", UUID("b2436d8f-206e-4ca1-990a-e7c4cadf8e3f"),
               0x046D, 0x0AF7, 0xFFA0, 0x0001, read_logitech),
)


def usb_devices():
    try:
        interfaces = hid.enumerate()
    except OSError:
        return []
    return [device for profile in USB_PROFILES if (device := profile.find(interfaces)) is not None]


def ble_level(payload):
    return payload[0] if len(payload) == 1 and payload[0] <= 100 else None


async def read_ble(address):
    async with asyncio.timeout(12):
        async with BleakClient(address, timeout=6, services=[BATTERY_SERVICE]) as client:
            service = client.services.get_service(BATTERY_SERVICE)
            if service is None:
                return None
            characteristic = service.get_characteristic(BATTERY_LEVEL)
            if characteristic is None or "read" not in characteristic.properties:
                return None
            return ble_level(await client.read_gatt_char(characteristic, use_cached=False))


def read_ble_battery(address):
    try:
        return asyncio.run(read_ble(address))
    except BLE_ERRORS:
        return None


async def scan_ble():
    return await BleakScanner.discover(timeout=6, return_adv=True)


def load_ble_devices(path: Path):
    if not path.exists():
        return []
    with path.open("rb") as handle:
        entries = tomllib.load(handle).get("bluetooth", [])
    if not isinstance(entries, list):
        raise ValueError("Expected one or more [[bluetooth]] tables.")
    devices = []
    addresses = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Bluetooth entry {index} must be a table.")
        name, kind, address = (entry.get(key) for key in ("name", "kind", "address"))
        if not isinstance(name, str) or not name.strip() or not isinstance(kind, str) or kind not in ("mouse", "headset"):
            raise ValueError(f"Bluetooth entry {index} needs a name and kind (mouse or headset).")
        if not isinstance(address, str) or not BLUETOOTH_ADDRESS.fullmatch(address.upper()):
            raise ValueError(f"Bluetooth entry {index} needs an address like AA:BB:CC:DD:EE:FF.")
        address = address.upper()
        if address in addresses:
            raise ValueError(f"Bluetooth entry {index} repeats an address.")
        addresses.add(address)
        icon_id = uuid5(NAMESPACE_URL, f"peripheral-battery-tray/ble/{address}")
        devices.append(Device(name.strip()[:85], kind, icon_id, lambda address=address: read_ble_battery(address)))
    return devices
