"""IPI Haze X Pro USB receiver."""

from uuid import UUID

from .transport import UsbProfile, read_paths

IPI_QUERY = bytes.fromhex("08 02 00 00 00 f5")


def ipi_level(report):
    if len(report) < 10 or report[:5] != b"\x08\x02\x00\x00\x04":
        return None
    if sum(report[:10]) % 256 != 255 or report[6] == 0:
        return None
    level = report[7] & 127
    # The IPI web driver treats zero in this status reply as a loading value.
    return level if 0 < level <= 100 else None


def matches_collection(device):
    # The receiver has two collections with the same usage.
    descriptor = bytes(device.get_report_descriptor())
    return b"\x85\x08" in descriptor and b"\x95\x3f\x91" in descriptor


def read_ipi(paths):
    return read_paths(paths, IPI_QUERY, ipi_level, matches=matches_collection)


PROFILE = UsbProfile(
    "IPI Haze X Pro", "mouse", UUID("47b3ec39-8bfb-4cc5-bb98-8d92e589df43"),
    0x372E, 0x10F9, 0xFF04, 0x0001, read_ipi,
)
