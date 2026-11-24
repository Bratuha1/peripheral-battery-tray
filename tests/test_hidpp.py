"""USB receiver and explicit USB discovery tests."""

import unittest
from unittest.mock import MagicMock, patch

import monitor
from profiles import hidpp


class HidppTests(unittest.TestCase):
    def test_only_a_matched_report_yields_a_payload(self):
        handle = MagicMock()
        handle.write.return_value = 20
        correct = bytes.fromhex("11 02 05 1b 4a").ljust(20, b"\0")
        handle.read.side_effect = [bytes.fromhex("11 01 05 1b 7f").ljust(20, b"\0"), correct]
        self.assertEqual(hidpp.exchange(handle, 2, 5, 1)[0], 74)
        self.assertEqual(handle.write.call_args.args[0][:4], bytes.fromhex("11 02 05 1b"))

    def test_matching_error_rejects_the_request(self):
        handle = MagicMock()
        handle.write.return_value = 20
        handle.read.return_value = bytes.fromhex("11 02 ff 05 1b 09").ljust(20, b"\0")
        self.assertIsNone(hidpp.exchange(handle, 2, 5, 1))

    def test_only_capability_backed_percentages_are_supported(self):
        with patch.object(hidpp, "feature_index", return_value=5), patch.object(hidpp, "exchange") as exchange:
            exchange.side_effect = [b"\x0f\x00"]
            self.assertIsNone(hidpp.read_percentage(None, 1))
            for raw, expected in [(0, 0), (100, 100), (101, None), (255, None)]:
                exchange.side_effect = [b"\x0f\x02", bytes([raw])]
                self.assertEqual(hidpp.read_percentage(None, 1), expected)

    def test_receiver_scan_targets_only_long_usb_collection_and_reuses_discovery(self):
        receiver = dict(vendor_id=0x046D, product_id=0xC548, bus_type=1, usage_page=0xFF00, usage=2,
                        path=b"long")
        discovery = hidpp.ReceiverDiscovery()
        with patch.object(discovery, "probe", return_value={1: "paired"}) as probe:
            self.assertEqual(discovery.devices([{**receiver, "usage": 1}, receiver]), ["paired"])
            self.assertEqual(discovery.devices([receiver]), ["paired"])
            probe.assert_called_once_with(b"long", receiver)
            self.assertEqual(discovery.devices([receiver], scan=True), ["paired"])
            self.assertEqual(probe.call_count, 2)
            self.assertEqual(discovery.devices([]), [])

    def test_usb_scan_is_independent_of_configured_bluetooth(self):
        with patch.object(monitor, "usb_devices", return_value=[]) as usb, patch.object(monitor, "poll_bluetooth") as ble:
            self.assertEqual(monitor.poll_devices([], {"11:22:33:44:55:66": "Example"}, "usb"), ([], {}, False))
            usb.assert_called_once_with(scan=True)
            ble.assert_not_called()
