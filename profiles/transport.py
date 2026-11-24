"""Common HID transport for registered USB battery profiles."""

from dataclasses import dataclass
import logging
from time import monotonic
from typing import Callable
from uuid import UUID

import hid


@dataclass(frozen=True)
class UsbProfile:
    name: str
    kind: str
    icon_id: UUID
    vendor_id: int
    product_id: int
    usage_page: int
    usage: int
    read: Callable[[tuple[bytes, ...]], int | None]

    def paths(self, interfaces):
        return tuple(i["path"] for i in interfaces if (
            i.get("vendor_id"), i.get("product_id"), i.get("usage_page"), i.get("usage")
        ) == (self.vendor_id, self.product_id, self.usage_page, self.usage) and i.get("path"))


def query_hid(device, request, parse, offline=b""):
    if device.write(request.ljust(64, b"\0")) != 64:
        return None
    deadline = monotonic() + 1
    while monotonic() < deadline:
        report = bytes(device.read(64, 100))
        if offline and report.startswith(offline):
            return None
        level = parse(report)
        if level is not None:
            return level
    return None


def read_paths(paths, request, parse, offline=b"", matches=None):
    for path in paths:
        device = hid.device()
        try:
            device.open_path(path)
            if matches is None or matches(device):
                return query_hid(device, request, parse, offline)
        except OSError:
            logging.debug("USB battery interface inaccessible")
        finally:
            device.close()
    return None
