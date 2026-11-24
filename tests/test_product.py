"""Tests for device state, discovery, alert policy, settings and visual limits."""

import asyncio
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import devices
import monitor
from monitor import LowBattery, Reading, merge_readings
from settings import Settings, load_settings, save_settings
from strings import STRINGS, translate
from visuals import render_icon


class SettingsTests(unittest.TestCase):
    def test_settings_save_and_load_including_zero_threshold_and_rgb_names(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "deep" / "settings.json"
            settings = Settings(
                autostart=True, start_minimized=True, interval=5, headset_threshold=0, show_percent=True,
                tray_mode="combined", theme="dark", language="ru", hidden=[str(uuid4())],
                bluetooth={"AA:BB:CC:DD:EE:FF": "Наушники"},
            )
            save_settings(path, settings)
            self.assertEqual(load_settings(path), settings)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_invalid_values_fall_back_independently(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            self.assertEqual(load_settings(path), Settings())
            path.write_text(json.dumps({
                "interval": True, "tray_mode": {}, "headset_threshold": -1, "language": "ru",
                "hidden": [False, "missing"], "bluetooth": {"bad": "No", "11:22:33:44:55:66": 3},
            }), encoding="utf-8")
            self.assertEqual(load_settings(path), Settings(language="ru"))
            path.write_text("{", encoding="utf-8")
            with self.assertLogs(level="ERROR"):
                self.assertEqual(load_settings(path), Settings())

    def test_failed_replace_preserves_previous_file(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            save_settings(path, Settings())
            with patch.object(Path, "replace", side_effect=OSError), self.assertRaises(OSError):
                save_settings(path, Settings(language="ru"))
            self.assertEqual(load_settings(path), Settings())
            self.assertEqual(list(path.parent.iterdir()), [path])


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.device = devices.Device("Example", "mouse", uuid4(), lambda: 14)
        self.key = str(self.device.icon_id)

    def test_disconnect_retains_last_success_time_without_stale_percentage(self):
        first = monitor.read_usb(self.device)
        history = merge_readings({}, [first])
        offline = merge_readings(history, [])
        self.assertEqual(offline[self.key], Reading(self.device, None, "disconnected", first.updated))
        late = Reading(self.device, 0, "connected", datetime(2026, 8, 1))
        self.assertEqual(merge_readings(offline, [late])[self.key], late)

    def test_unavailable_retains_last_success_time(self):
        old = monitor.read_usb(self.device)
        current = Reading(self.device, None, "unavailable")
        history = merge_readings({self.key: old}, [current])
        self.assertEqual(history[self.key], replace(current, updated=old.updated))

    def test_alert_latches_across_disconnect_and_rearms_with_hysteresis(self):
        policy = LowBattery()
        settings = Settings(mouse_threshold=21)

        def update(level):
            return policy.update({self.key: Reading(self.device, level, "connected")}, settings)

        self.assertEqual(len(update(20)), 1)
        for value in (20, None, 20, 21, 22, 23, 20):
            self.assertEqual(update(value), [])
        self.assertEqual(update(24), [])
        self.assertEqual(len(update(20)), 1)

    def test_alert_can_be_disabled_and_hidden_devices_do_not_warn(self):
        policy = LowBattery()
        readings = {self.key: Reading(self.device, 0, "connected")}
        self.assertEqual(policy.update(readings, Settings(mouse_threshold=0)), [])
        self.assertEqual(policy.update(readings, Settings(hidden=[self.key])), [])
        self.assertEqual(len(policy.update(readings, Settings())), 1)

    def test_discovery_verifies_service_and_accepts_an_exact_zero(self):
        addresses = [f"00:11:22:33:44:{number:02X}" for number in range(4)]
        advertisements = {
            address: (SimpleNamespace(name=f"Device {index}", address=address),
                      SimpleNamespace(local_name=None, service_uuids=[devices.BATTERY_SERVICE] if index != 3 else []))
            for index, address in enumerate(addresses)
        }
        configured = {addresses[3]: devices.bluetooth_device("Configured", "headset", addresses[3])}

        async def read(target):
            return {addresses[0]: 0, addresses[1]: None, addresses[2]: None, addresses[3]: 61}[target.address]

        with patch.object(monitor, "scan_ble", new=AsyncMock(return_value=advertisements)), \
                patch.object(monitor, "read_ble", side_effect=read):
            readings, found, failed = asyncio.run(monitor.poll_bluetooth(configured, True))
        self.assertFalse(failed)
        self.assertEqual(found, {addresses[0]: "Device 0"})
        self.assertEqual([(reading.device.name, reading.level) for reading in readings],
                         [("Configured", 61), ("Device 0", 0)])

    def test_ordinary_poll_uses_one_scan_and_reports_missing_advertisements(self):
        address = "00:11:22:33:44:55"
        configured = {address: devices.bluetooth_device("Example", "mouse", address)}
        with patch.object(monitor, "scan_ble", new=AsyncMock(return_value={})) as scan, \
                patch.object(monitor, "read_ble") as read:
            readings, found, failed = asyncio.run(monitor.poll_bluetooth(configured, False))
        scan.assert_awaited_once()
        read.assert_not_called()
        self.assertEqual(readings[0].status, "disconnected")
        self.assertFalse(found or failed)

    def test_disabled_radio_keeps_configured_device_unavailable(self):
        address = "00:11:22:33:44:55"
        configured = {address: devices.bluetooth_device("Example", "mouse", address)}
        with patch.object(monitor, "scan_ble", side_effect=TimeoutError), self.assertLogs(level="WARNING"):
            readings, found, failed = asyncio.run(monitor.poll_bluetooth(configured, True))
        self.assertTrue(failed)
        self.assertEqual(found, {})
        self.assertEqual(readings[0].status, "unavailable")


class ProfileAndVisualTests(unittest.TestCase):
    def test_only_matching_usb_collections_are_read_and_ids_are_stable(self):
        profile = devices.USB_PROFILES[0]
        item = dict(vendor_id=profile.vendor_id, product_id=profile.product_id,
                    usage_page=profile.usage_page, usage=profile.usage)
        with patch.object(devices.hid, "enumerate", return_value=[
            {**item, "path": b"wrong", "usage": 2},
            {**item, "path": b"first"},
            {**item, "path": b"second"},
        ]), patch("profiles.ipi.read_paths", return_value=42) as read:
            device, = devices.usb_devices()
            self.assertEqual(str(device.icon_id), "47b3ec39-8bfb-4cc5-bb98-8d92e589df43")
            self.assertEqual(device.read(), 42)
        self.assertEqual(read.call_args.args[0], (b"first", b"second"))

    def test_logitech_ignores_wrong_feature_operation(self):
        wrong = bytes.fromhex("51 0b 00 03 10 00 06 00 04 0b 43 43 00")
        self.assertIsNone(devices.logitech_level(wrong))

    def test_ble_timeout_returns_unavailable(self):
        with patch.object(devices, "read_ble", side_effect=TimeoutError):
            self.assertIsNone(devices.read_ble_battery("AA:BB:CC:DD:EE:FF"))

    def test_numeric_badges_and_localization_are_renderable(self):
        for level in [0, 1, 99, 100]:
            for kind in ("mouse", "headset", "other"):
                with self.subTest(level=level, kind=kind):
                    self.assertEqual(render_icon(kind, level, 15, True).size, (32, 32))
        self.assertNotEqual(render_icon("mouse", 100, 15, True).tobytes(),
                            render_icon("mouse", 100, 15, False).tobytes())
        for key in STRINGS:
            self.assertTrue(translate("en", key))
            self.assertTrue(translate("ru", key))


if __name__ == "__main__":
    unittest.main()
