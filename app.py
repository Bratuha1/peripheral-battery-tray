"""Windows desktop application lifecycle and background polling."""

from dataclasses import replace
import logging
import os
from queue import Empty, SimpleQueue
from threading import Thread
import tkinter as tk

from devices import bluetooth_device
from monitor import LowBattery, merge_readings, poll_devices
from settings import APP_NAME, Settings, save_settings
from strings import translate
from tray import APP_ID, IconSpec, Tray
from ui import SettingsWindow
from windows import set_autostart, system_language


class BatteryApp:
    def __init__(self, root, settings, path, configured, config_error=False):
        self.root = root
        self.settings, self.path, self.configured = settings, path, configured
        self.config_error = config_error
        self.status = "config_error" if config_error else "ready"
        self.scanning = self.pending_scan = None
        self.running = self.pending = False
        self.timer = self.resume_timer = None
        self.readings = {}
        self.alerts = LowBattery()
        self.results = SimpleQueue()
        self.generation = 0
        self.actions = SimpleQueue()
        self.tray = Tray(self.actions.put, self.menu)
        try:
            self.window = SettingsWindow(root, self)
        except Exception:
            self.tray.close()
            raise

    @property
    def language(self):
        return system_language() if self.settings.language == "system" else self.settings.language

    def t(self, key):
        return translate(self.language, key)

    def name(self, device):
        return device.name or ("Устройство Bluetooth LE" if self.language == "ru" else "Bluetooth LE device")

    def report_callback_exception(self, kind, error, traceback):
        logging.error("Window callback failed", exc_info=(kind, error, traceback))
        self.status = "poll_error"
        self.window.set_status()

    def run(self, minimized):
        self.root.report_callback_exception = self.report_callback_exception
        tray_ready = self.sync_tray()
        if not minimized or not tray_ready:
            self.show_window()
        self.root.after_idle(self.request_poll)
        self.root.after(250, self.dispatch_pending)
        try:
            self.root.mainloop()
        finally:
            self.tray.close()

    def menu(self):
        style = "battery" if self.settings.icon_style == "device" else "device"
        items = [(self.t(key), key) for key in ("show", "refresh", "scan_usb", "scan_ble")]
        items.append((self.t(f"tray_{style}"), f"style_{style}"))
        return [*items, (self.t("pin_tray"), "pin_tray"), (self.t("exit"), "exit")]

    def dispatch_pending(self):
        # A native window procedure can interrupt Tcl's message loop.
        # Run Tk operations only from a Tk timer, after the procedure returns.
        self.root.after(250, self.dispatch_pending)
        actions = {
            "show": self.show_window,
            "refresh": self.request_poll,
            "scan_usb": lambda: self.request_poll(discover="usb"),
            "scan_ble": lambda: self.request_poll(discover="ble"),
            "style_device": lambda: self.change_settings(icon_style="device"),
            "style_battery": lambda: self.change_settings(icon_style="battery"),
            "pin_tray": self.open_tray_settings,
            "exit": self.root.quit,
            "theme": self.theme_changed,
            "resume": self.resumed,
            "poll_ready": self.finish_poll,
        }
        while True:
            try:
                action = self.actions.get_nowait()
            except Empty:
                return
            actions[action]()
            if action == "exit":
                return

    def show_window(self):
        self.window.render_devices()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        if self.sync_tray():
            self.root.withdraw()

    def theme_changed(self):
        if self.settings.theme == "system" and self.window.dark != self.window.is_dark():
            self.window.rebuild()

    def resumed(self):
        if self.resume_timer is not None:
            self.root.after_cancel(self.resume_timer)

        def refresh():
            self.resume_timer = None
            logging.info("System resumed; refreshing devices")
            self.request_poll()

        self.resume_timer = self.root.after(1800, refresh)

    def schedule_poll(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
        self.timer = self.root.after(self.settings.interval * 1000, self.request_poll)

    def request_poll(self, discover=None):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.running:
            self.pending = True
            self.pending_scan = discover or self.pending_scan
            return
        self.running, self.scanning = True, discover
        self.status = {"usb": "scanning_usb", "ble": "scanning"}.get(discover, "working")
        self.window.set_status()
        generation = self.generation
        saved = dict(self.settings.bluetooth)

        def work():
            try:
                result = poll_devices(self.configured, saved, discover)
            except Exception:
                logging.exception("Device polling failed")
                result = None
            self.results.put((generation, result))
            self.actions.put("poll_ready")

        Thread(target=work, name="battery-poll", daemon=True).start()

    def finish_poll(self):
        generation, result = self.results.get_nowait()
        self.running = False
        scanning, self.scanning = self.scanning, None
        self.status = "config_error" if self.config_error else "ready"
        if result is None:
            self.status = "poll_error"
        elif generation == self.generation:
            readings, found, scan_failed = result
            if scanning == "usb":
                # A USB-only search should not change existing Bluetooth readings.
                readings.extend(reading for reading in self.readings.values() if reading.device.address)
                self.status = "usb_scan_done" if any(not reading.device.address for reading in readings) else "usb_scan_empty"
            elif scanning == "ble":
                self.status = "scan_failed" if scan_failed else "scan_done"
            self.readings = merge_readings(self.readings, readings)
            if found:
                self.change_settings(bluetooth={**self.settings.bluetooth, **found})
            self.sync_tray()
            self.send_alerts()
            if self.root.state() == "normal":
                self.window.render_devices()
        self.window.set_status()
        if self.pending:
            discover = self.pending_scan
            self.pending = False
            self.pending_scan = None
            self.request_poll(discover)
        else:
            self.schedule_poll()

    def sync_tray(self):
        visible = [(reading, self.settings.threshold(reading.device.kind))
                   for key, reading in self.readings.items() if key not in self.settings.hidden]
        desired = {}
        if self.settings.tray_mode == "separate":
            for reading, threshold in visible:
                level = reading.level
                status = f"{level}%" if level is not None else self.t(reading.status)
                desired[reading.device.icon_id] = IconSpec(f"{self.name(reading.device)} · {status}",
                                                           reading.device.kind if self.settings.icon_style == "device" else "other",
                                                           level, threshold,
                                                           self.settings.show_percent)
        if not desired:
            measured = [(reading, threshold) for reading, threshold in visible if reading.level is not None]
            lines = [f"{self.name(reading.device)}: {reading.level}%" for reading, _ in measured]
            title = "\n".join(lines) or APP_NAME
            if self.settings.show_percent and measured:
                reading, threshold = min(measured, key=lambda pair: pair[0].level)
                desired[APP_ID] = IconSpec(title, "other", reading.level, threshold, True)
            else:
                desired[APP_ID] = IconSpec(title, "app")
        try:
            success = self.tray.sync(desired)
        except OSError:
            logging.exception("Could not update notification area")
            success = False
        if not success:
            self.status = "tray_error"
            self.window.set_status()
            self.show_window()
        return success

    def send_alerts(self):
        alerts = self.alerts.update(self.readings, self.settings)
        if alerts:
            lines = "\n".join(f"{self.name(reading.device)}: {reading.level}%" for reading in alerts)
            if not self.tray.notify(self.t("low"), lines):
                logging.warning("Windows did not accept the low battery notification")
                self.alerts.warned.difference_update(str(reading.device.icon_id) for reading in alerts)

    def persist(self, settings):
        previous = self.settings
        startup_changed = settings.autostart != previous.autostart
        try:
            if startup_changed:
                set_autostart(settings.autostart)
            save_settings(self.path, settings)
        except OSError:
            logging.exception("Could not save settings")
            if startup_changed:
                try:
                    set_autostart(previous.autostart)
                except OSError:
                    logging.exception("Could not restore startup registration")
            self.status = "save_error"
            self.window.set_status()
            return False
        self.settings = settings
        return True

    def change_settings(self, **changes):
        new = replace(self.settings, **changes)
        if new == self.settings:
            return True
        if not self.persist(new):
            return False
        if "theme" in changes or "language" in changes:
            self.window.rebuild()
        if "interval" in changes and not self.running:
            self.schedule_poll()
        if changes.keys() & {"tray_mode", "icon_style", "show_percent", "language", "hidden",
                             "mouse_threshold", "headset_threshold", "other_threshold"}:
            self.sync_tray()
            self.send_alerts()
        if "hidden" in changes:
            self.window.render_devices()
        return True

    def change_checkbox(self, key, value):
        if not self.change_settings(**{key: value.get()}):
            value.set(getattr(self.settings, key))

    def toggle_device(self, key):
        hidden = set(self.settings.hidden)
        hidden.symmetric_difference_update({key})
        self.change_settings(hidden=sorted(hidden))

    def reset_settings(self):
        configured = {device.address for device in self.configured}
        forgotten = [str(bluetooth_device(name, "other", address).icon_id)
                     for address, name in self.settings.bluetooth.items() if address not in configured]
        if self.persist(Settings()):
            self.generation += 1
            for key in forgotten:
                self.readings.pop(key, None)
                self.alerts.warned.discard(key)
            self.window.show_hidden = False
            self.window.rebuild()
            self.sync_tray()
            self.request_poll()

    def open_tray_settings(self):
        try:
            os.startfile("ms-settings:taskbar")
            self.status = "pin_help"
            self.window.set_status()
        except OSError:
            logging.exception("Could not open Windows taskbar settings")
            self.status = "pin_help"
            self.window.set_status()

    def open_log(self):
        try:
            os.startfile(self.path.parent)
        except OSError:
            logging.exception("Could not open the log directory")
