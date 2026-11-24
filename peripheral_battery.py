"""Display peripheral battery status in the Windows notification area."""

import argparse
import asyncio
import logging
from pathlib import Path
import sys

import hid

from devices import BATTERY_SERVICE, BLE_ERRORS, load_ble_devices, scan_ble, usb_devices
from settings import APP_DATA, APP_NAME, VERSION, configure_logging, load_settings, save_settings


def list_hid():
    for interface in hid.enumerate():
        if interface.get("bus_type") != 1 or interface.get("usage_page", 0) < 0xFF00:
            continue
        print(f'{interface["vendor_id"]:04X}:{interface["product_id"]:04X} '
              f'usage {interface["usage_page"]:04X}:{interface["usage"]:04X} '
              f'{interface.get("product_string") or "(unnamed)"}')


def config_path(explicit):
    if explicit is not None:
        if not explicit.is_file():
            raise ValueError("The specified Bluetooth configuration file does not exist.")
        return explicit
    location = APP_DATA / "devices.toml"
    if location.is_file():
        return location
    executable = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
    return executable.with_name("devices.toml")


def run_desktop(args):
    import tkinter as tk
    from app import BatteryApp
    from windows import activate_instance, autostart_enabled, set_autostart, single_instance

    with single_instance() as first:
        if not first:
            if not args.autostart:
                activate_instance()
            return
        configure_logging(APP_DATA)
        logging.info("%s %s started", APP_NAME, VERSION)
        path = APP_DATA / "settings.json"
        settings = load_settings(path)
        try:
            if args.enable_autostart or not path.exists():
                set_autostart(True)
                settings.autostart = True
                save_settings(path, settings)
            else:
                settings.autostart = autostart_enabled()
        except OSError:
            logging.exception("Could not read the Windows startup entry")
        configured, config_error = [], False
        try:
            configured = load_ble_devices(config_path(args.config))
        except (OSError, ValueError) as error:
            logging.error("Bluetooth configuration could not be loaded (%s)", type(error).__name__)
            config_error = True
        root = tk.Tk()
        root.withdraw()
        try:
            app = BatteryApp(root, settings, path, configured, config_error)
            app.run((args.autostart or settings.start_minimized) and not args.show)
        except Exception:
            logging.exception("Application stopped unexpectedly")
            raise
        finally:
            root.destroy()
            logging.info("Application stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="path to a Bluetooth configuration file")
    parser.add_argument("--enable-autostart", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="print one reading per device")
    mode.add_argument("--list-hid", action="store_true", help="list vendor-defined USB HID interfaces")
    mode.add_argument("--scan-ble", action="store_true", help="list advertising BLE devices")
    mode.add_argument("--show", action="store_true", help="show the window even when start minimized is enabled")
    mode.add_argument("--autostart", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.list_hid:
        list_hid()
    elif args.scan_ble:
        try:
            advertisements = asyncio.run(scan_ble())
        except BLE_ERRORS as error:
            parser.exit(1, f"Bluetooth scan failed: {error}\n")
        if not advertisements:
            print("No Bluetooth LE devices advertised during the scan.")
        for address, (device, data) in advertisements.items():
            service = " [advertises Battery Service]" if BATTERY_SERVICE in data.service_uuids else ""
            print(f"{address}  {device.name or data.local_name or '(unnamed)'}{service}")
    elif args.check:
        try:
            configured = load_ble_devices(config_path(args.config))
        except (OSError, ValueError) as error:
            parser.exit(2, f"Invalid device configuration: {error}\n")
        devices = (*usb_devices(), *configured)
        if not devices:
            parser.exit(1, "No supported device found. Run --list-hid or --scan-ble.\n")
        for device in devices:
            level = device.read()
            print(f"{device.name}: {'unavailable' if level is None else f'{level}%'}")
    else:
        run_desktop(args)


if __name__ == "__main__":
    main()
