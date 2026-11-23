"""Display peripheral battery status in the Windows notification area."""

import argparse
import asyncio
import ctypes
from ctypes import wintypes
from pathlib import Path
from threading import Event

import hid
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem
from pystray._util import win32

from devices import BATTERY_SERVICE, BLE_ERRORS, load_ble_devices, scan_ble, usb_devices


LOW_BATTERY = 15
POLL_SECONDS = 20
CONFIG = Path(__file__).with_name("devices.toml")


class DeviceIcon(Icon):
    def __init__(self, icon_id, *args):
        super().__init__(*args)
        self.tray_id = win32.NOTIFYICONDATAW.GUID.from_buffer_copy(icon_id.bytes_le)

    def _message(self, code, flags, **kwargs):
        # Windows remembers the visibility of each device across app launches.
        win32.Shell_NotifyIcon(code, win32.NOTIFYICONDATAW(
            cbSize=ctypes.sizeof(win32.NOTIFYICONDATAW),
            hWnd=self._hwnd,
            uID=1,
            uFlags=flags | win32.NIF_GUID,
            guidItem=self.tray_id,
            **kwargs,
        ))


def draw_mouse(level):
    image = Image.new("RGBA", (16, 16))
    draw = ImageDraw.Draw(image)
    color = "#aeb8c4" if level is None else "#ff8a8f" if level < LOW_BATTERY else "#b5dfff"
    draw.rounded_rectangle((3, 0, 12, 15), radius=5, outline=color, width=2)
    draw.line((7, 2, 7, 5), fill=color, width=2)
    return image.resize((32, 32), Image.Resampling.NEAREST)


def draw_headset(level):
    image = Image.new("RGBA", (16, 16))
    draw = ImageDraw.Draw(image)
    color = "#aeb8c4" if level is None else "#ff8a8f" if level < LOW_BATTERY else "#d9ffe4"
    draw.arc((2, 1, 13, 12), 180, 360, fill=color, width=2)
    draw.line((2, 6, 2, 11), fill=color, width=2)
    draw.line((13, 6, 13, 11), fill=color, width=2)
    draw.rounded_rectangle((2, 8, 5, 14), radius=1, fill=color)
    draw.rounded_rectangle((10, 8, 13, 14), radius=1, fill=color)
    return image.resize((32, 32), Image.Resampling.NEAREST)


def tray(configured_devices):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    mutex = kernel.CreateMutexW(None, False, "Local\\PeripheralBatteryTray")
    error = ctypes.get_last_error()
    if not mutex:
        raise ctypes.WinError(error)
    if error == 183:
        kernel.CloseHandle(mutex)
        return

    refresh = Event()
    stopped = Event()
    icons = {}
    readings = {}
    renderers = {"mouse": draw_mouse, "headset": draw_headset}

    def refresh_menu(icon, item):
        refresh.set()

    def quit_menu(icon, item):
        stopped.set()
        refresh.set()

    menu = Menu(MenuItem("Refresh battery", refresh_menu), MenuItem("Exit", quit_menu))
    try:
        while not stopped.is_set():
            refresh.clear()
            detected = {item.icon_id: item for item in (*usb_devices(), *configured_devices)}
            for icon_id in icons.keys() - detected.keys():
                icons.pop(icon_id).stop()
                readings.pop(icon_id, None)
            for icon_id, device in detected.items():
                if stopped.is_set():
                    break
                render = renderers[device.kind]
                if icon_id not in icons:
                    icon = DeviceIcon(icon_id, device.name, render(None), device.name, menu)
                    icon.run_detached()
                    icons[icon_id] = icon
                level = device.read()
                if icon_id not in readings or level != readings[icon_id]:
                    readings[icon_id] = level
                    status = "Battery unavailable" if level is None else f"{level}%"
                    icons[icon_id].title = f"{device.name} · {status}"
                    icons[icon_id].icon = render(level)
            if stopped.is_set():
                break
            refresh.wait(POLL_SECONDS)
    finally:
        for icon in icons.values():
            icon.stop()
        kernel.CloseHandle(mutex)


def list_hid():
    for interface in hid.enumerate():
        if interface.get("bus_type") != 1 or interface["usage_page"] < 0xFF00:
            continue
        print(f'{interface["vendor_id"]:04X}:{interface["product_id"]:04X} '
              f'usage {interface["usage_page"]:04X}:{interface["usage"]:04X} '
              f'{interface.get("product_string") or "(unnamed)"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="path to a Bluetooth configuration file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="print one reading per device")
    mode.add_argument("--list-hid", action="store_true", help="list vendor-defined USB HID interfaces")
    mode.add_argument("--scan-ble", action="store_true", help="list devices advertising over Bluetooth LE")
    args = parser.parse_args()

    if args.list_hid:
        list_hid()
        return
    if args.scan_ble:
        try:
            advertisements = asyncio.run(scan_ble())
        except BLE_ERRORS as error:
            parser.exit(1, f"Bluetooth scan failed: {error}\n")
        if not advertisements:
            print("No Bluetooth LE devices advertised during the scan.")
        for address, (device, data) in advertisements.items():
            battery = " [advertises Battery Service]" if BATTERY_SERVICE in data.service_uuids else ""
            print(f"{address}  {device.name or data.local_name or '(unnamed)'}{battery}")
        return

    try:
        if args.config is not None and not args.config.is_file():
            parser.error("The specified Bluetooth configuration file does not exist.")
        configured = load_ble_devices(args.config or CONFIG)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Invalid device configuration: {error}\n")
    devices = (*usb_devices(), *configured)
    if not devices:
        parser.exit(1, "No supported device found. Run --list-hid or --scan-ble; see the device guide.\n")
    if args.check:
        for device in devices:
            level = device.read()
            print(f"{device.name}: {'unavailable' if level is None else f'{level}%'}")
    else:
        tray(configured)


if __name__ == "__main__":
    main()
