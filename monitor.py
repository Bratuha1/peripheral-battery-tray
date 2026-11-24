"""Device polling, reading history and low-battery notification policy."""

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime
import logging

from devices import (
    BATTERY_SERVICE, BLE_ERRORS, BLUETOOTH_ADDRESS, Device,
    bluetooth_device, read_ble, scan_ble, usb_devices,
)


@dataclass(frozen=True)
class Reading:
    device: Device
    level: int | None
    status: str
    updated: datetime | None = None


def read_usb(device):
    try:
        level = device.read()
    except Exception:
        logging.exception("USB battery read failed for %s", device.name)
        level = None
    return Reading(device, level, "connected" if level is not None else "unavailable",
                   datetime.now() if level is not None else None)


async def poll_bluetooth(configured, discover):
    try:
        observed = {address.upper(): value for address, value in (await scan_ble()).items()}
    except BLE_ERRORS as error:
        logging.warning("Bluetooth scan failed (%s)", type(error).__name__)
        return [Reading(device, None, "unavailable") for device in configured.values()], {}, True

    candidates = dict(configured)
    for address, (target, advert) in observed.items():
        name = (target.name or advert.local_name or "").strip()[:85]
        if (discover and address not in candidates and BLUETOOTH_ADDRESS.fullmatch(address)
                and BATTERY_SERVICE in advert.service_uuids):
            candidates[address] = bluetooth_device(name, "other", address)

    limit = asyncio.Semaphore(3)

    async def measure(address, device):
        if address not in observed:
            return Reading(device, None, "disconnected")
        async with limit:
            try:
                level = await read_ble(observed[address][0])
            except BLE_ERRORS as error:
                logging.debug("Bluetooth read failed (%s)", type(error).__name__)
                level = None
            except Exception as error:
                logging.error("Unexpected Bluetooth read failure (%s)", type(error).__name__)
                level = None
        return Reading(device, level, "connected" if level is not None else "unavailable",
                       datetime.now() if level is not None else None)

    readings = await asyncio.gather(*(measure(address, device) for address, device in candidates.items()))
    found = {
        address: reading.device.name
        for address, reading in zip(candidates, readings)
        if address not in configured and reading.level is not None
    }
    return [reading for address, reading in zip(candidates, readings)
            if address in configured or address in found], found, False


def poll_devices(configured, saved, discover=None):
    readings = [read_usb(device) for device in usb_devices(scan=discover == "usb")]
    bluetooth = {address: bluetooth_device(name, "other", address) for address, name in saved.items()}
    bluetooth.update({device.address: device for device in configured})
    if discover == "ble" or (bluetooth and discover != "usb"):
        ble, found, scan_failed = asyncio.run(poll_bluetooth(bluetooth, discover == "ble"))
        return readings + ble, found, scan_failed
    return readings, {}, False


def merge_readings(previous, current, forgotten=()):
    readings = {
        key: replace(reading, level=None, status="disconnected")
        for key, reading in previous.items() if key not in forgotten
    }
    for reading in current:
        key = str(reading.device.icon_id)
        if reading.updated is None and key in readings:
            reading = replace(reading, updated=readings[key].updated)
        readings[key] = reading
    return readings


class LowBattery:
    """Alert once per low episode, including across temporary disconnects."""

    def __init__(self):
        self.warned = set()

    def update(self, readings, settings):
        alerts = []
        for key, reading in readings.items():
            threshold = settings.threshold(reading.device.kind)
            if threshold == 0:
                self.warned.discard(key)
            elif reading.level is not None:
                if reading.level >= min(100, threshold + 3):
                    self.warned.discard(key)
                elif reading.level < threshold and key not in self.warned and key not in settings.hidden:
                    self.warned.add(key)
                    alerts.append(reading)
        return alerts
