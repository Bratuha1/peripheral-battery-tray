from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import devices


class BatteryTests(unittest.TestCase):
    def test_ipi_checks_checksum_and_ignores_loading_zero(self):
        reading = bytes.fromhex("08 02 00 00 04 01 01 22 00 cd")
        charging = bytes.fromhex("08 02 00 00 04 01 01 a2 00 4d")
        loading = bytes.fromhex("08 02 00 00 04 01 01 00 00 ef")
        self.assertEqual(devices.ipi_level(reading), 34)
        self.assertEqual(devices.ipi_level(charging), 34)
        self.assertIsNone(devices.ipi_level(loading))
        self.assertIsNone(devices.ipi_level(reading[:-1] + b"\x00"))

    def test_logitech_battery_response(self):
        report = bytes.fromhex("51 0b 00 03 10 00 06 00 04 0a 43 43 00")
        self.assertEqual(devices.logitech_level(report), 67)
        self.assertIsNone(devices.logitech_level(devices.LOGITECH_OFFLINE))

    def test_ble_zero_is_valid(self):
        self.assertEqual(devices.ble_level(bytes([0])), 0)
        self.assertEqual(devices.ble_level(bytes([100])), 100)
        self.assertIsNone(devices.ble_level(bytes([255])))
        self.assertIsNone(devices.ble_level(b""))

    def test_ble_reads_standard_characteristic(self):
        with patch.object(devices, "BleakClient") as client_factory:
            client = client_factory.return_value.__aenter__.return_value
            client.services = MagicMock()
            service = client.services.get_service.return_value
            characteristic = service.get_characteristic.return_value
            characteristic.properties = ["read"]
            client.read_gatt_char = AsyncMock(return_value=bytearray([54]))
            self.assertEqual(devices.read_ble_battery("00:11:22:33:44:55"), 54)
            client.read_gatt_char.assert_awaited_once_with(characteristic, use_cached=False)
            service.get_characteristic.assert_called_once_with(devices.BATTERY_LEVEL)

    def test_config_validates_and_normalizes_addresses(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "devices.toml"
            self.assertEqual(devices.load_ble_devices(path), [])
            entry = '[[bluetooth]]\nname = "Example"\nkind = "mouse"\naddress = "aa:bb:cc:dd:ee:ff"\n'
            path.write_text(entry, encoding="utf-8")
            device, = devices.load_ble_devices(path)
            with patch.object(devices, "read_ble_battery", return_value=77) as read:
                self.assertEqual(device.read(), 77)
                read.assert_called_once_with("AA:BB:CC:DD:EE:FF")
            path.write_text(entry * 2, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "repeats"):
                devices.load_ble_devices(path)
