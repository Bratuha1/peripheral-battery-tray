"""Logitech G PRO X 2 LIGHTSPEED USB receiver."""

from uuid import UUID

from .transport import UsbProfile, read_paths

LOGITECH_QUERY = bytes.fromhex("51 08 00 03 1a 00 03 00 04 0a")
LOGITECH_OFFLINE = bytes.fromhex("51 05 00 ff 03 1a 0b 00")


def logitech_level(report):
    if len(report) >= 13 and report[:2] == b"\x51\x0b" and report[8:10] == b"\x04\x0a":
        return report[10] if report[10] <= 100 else None
    return None


def read_logitech(paths):
    return read_paths(paths, LOGITECH_QUERY, logitech_level, LOGITECH_OFFLINE)


PROFILE = UsbProfile(
    "Logitech G PRO X 2 LIGHTSPEED", "headset", UUID("b2436d8f-206e-4ca1-990a-e7c4cadf8e3f"),
    0x046D, 0x0AF7, 0xFFA0, 0x0001, read_logitech,
)
