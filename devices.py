"""Battery readers for registered USB receivers and the BLE Battery Service."""

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import re
import tomllib
from typing import Callable
from uuid import NAMESPACE_URL, UUID, uuid5

import hid
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from profiles import USB_PROFILES
from profiles.hidpp import ReceiverDiscovery
from profiles.ipi import ipi_level
from profiles.logitech import LOGITECH_OFFLINE, logitech_level

BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
BLE_ERRORS = (BleakError, OSError, TimeoutError)
BLUETOOTH_ADDRESS = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", re.ASCII)


@dataclass(frozen=True)
class Device:
    name: str
    kind: str
    icon_id: UUID
    read: Callable[[], int | None]
    address: str | None = None


receiver_discovery = ReceiverDiscovery()


def usb_devices(scan=False):
    try:
        interfaces = hid.enumerate()
    except OSError:
        logging.warning("Could not enumerate USB HID interfaces")
        return []
    devices = []
    for profile in USB_PROFILES:
        paths = profile.paths(interfaces)
        if paths:
            devices.append(Device(
                profile.name, profile.kind, profile.icon_id,
                lambda profile=profile, paths=paths: profile.read(paths),
            ))
    for peripheral in receiver_discovery.devices(interfaces, scan=scan):
        devices.append(Device(peripheral.name, peripheral.kind, peripheral.icon_id, peripheral.read))
    return devices


def ble_level(payload):
    return payload[0] if len(payload) == 1 and payload[0] <= 100 else None


async def read_ble(target):
    async with asyncio.timeout(12):
        async with BleakClient(target, timeout=6, services=[BATTERY_SERVICE]) as client:
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
    async with asyncio.timeout(10):
        return await BleakScanner.discover(timeout=6, return_adv=True)


def bluetooth_device(name, kind, address):
    icon_id = uuid5(NAMESPACE_URL, f"peripheral-battery-tray/ble/{address}")
    return Device(name, kind, icon_id, lambda: read_ble_battery(address), address)


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
        if not isinstance(name, str) or not name.strip() or kind not in ("mouse", "headset", "other"):
            raise ValueError(f"Bluetooth entry {index} needs a name and kind (mouse, headset or other).")
        if not isinstance(address, str) or not BLUETOOTH_ADDRESS.fullmatch(address.upper()):
            raise ValueError(f"Bluetooth entry {index} needs an address like AA:BB:CC:DD:EE:FF.")
        address = address.upper()
        if address in addresses:
            raise ValueError(f"Bluetooth entry {index} repeats an address.")
        addresses.add(address)
        devices.append(bluetooth_device(name.strip()[:85], kind, address))
    return devices
