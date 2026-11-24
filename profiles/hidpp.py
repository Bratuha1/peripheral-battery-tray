"""Read the HID++ 2.0 Unified Battery feature over Logitech USB receivers."""

from dataclasses import dataclass
from time import monotonic
from uuid import NAMESPACE_URL, UUID, uuid5

import hid


RECEIVERS = {
    0xC548: "Logi Bolt", 0xC52B: "Logitech Unifying", 0xC532: "Logitech Unifying",
    0xC539: "Logitech LIGHTSPEED", 0xC53A: "Logitech LIGHTSPEED", 0xC53D: "Logitech LIGHTSPEED",
    0xC53F: "Logitech LIGHTSPEED", 0xC541: "Logitech LIGHTSPEED", 0xC545: "Logitech LIGHTSPEED",
    0xC547: "Logitech LIGHTSPEED", 0xC54D: "Logitech LIGHTSPEED",
}
SOFTWARE_ID = 0x0B
REPLY_TIMEOUT = 0.35


def exchange(handle, slot, feature, function, payload=b""):
    header = bytes((0x11, slot, feature, function << 4 | SOFTWARE_ID))
    if handle.write((header + payload).ljust(20, b"\0")) != 20:
        return None
    deadline = monotonic() + REPLY_TIMEOUT
    while (remaining := deadline - monotonic()) > 0:
        reply = bytes(handle.read(20, max(1, round(remaining * 1000))))
        if len(reply) == 20 and reply.startswith(header):
            return reply[4:]
        if (len(reply) in (7, 20) and reply[0] in (0x10, 0x11) and reply[1] == slot
                and reply[2] in (0x8F, 0xFF) and reply[3:5] == header[2:4]):
            return None
    return None


def feature_index(handle, slot, feature):
    reply = exchange(handle, slot, 0, 0, feature.to_bytes(2, "big"))
    return reply[0] if reply and 0 < reply[0] < 0xFF else None


def read_percentage(handle, slot):
    index = feature_index(handle, slot, 0x1004)
    if index is None:
        return None
    caps = exchange(handle, slot, index, 0)
    # Bit 1 explicitly confirms a real state-of-charge percentage.
    if caps is None or not caps[1] & 2:
        return None
    status = exchange(handle, slot, index, 1)
    return status[0] if status and status[0] <= 100 else None


@dataclass(frozen=True)
class Peripheral:
    name: str
    kind: str
    icon_id: UUID
    path: bytes
    slot: int

    def read(self):
        handle = hid.device()
        try:
            handle.open_path(self.path)
            return read_percentage(handle, self.slot)
        except OSError:
            return None
        finally:
            handle.close()


def describe(handle, slot, receiver):
    index = feature_index(handle, slot, 0x0005)
    name = f"{receiver} · {slot}"
    kind = "other"
    if index is None:
        return name, kind
    count = exchange(handle, slot, index, 0)
    if count and 0 < count[0] <= 64:
        data = bytearray()
        while len(data) < count[0]:
            chunk = exchange(handle, slot, index, 1, bytes((len(data),)))
            if chunk is None:
                break
            data.extend(chunk)
        if len(data) >= count[0]:
            decoded = data[:count[0]].decode("utf-8", errors="replace")
            name = "".join(char for char in decoded if char.isprintable()).strip() or name
    device_type = exchange(handle, slot, index, 2)
    if device_type and device_type[0] in (3, 4, 5):
        kind = "mouse"
    return name, kind


class ReceiverDiscovery:
    def __init__(self):
        self.known = {}

    def devices(self, interfaces, scan=False):
        active = {
            item["path"]: item for item in interfaces
            if item.get("vendor_id") == 0x046D and item.get("product_id") in RECEIVERS
            and item.get("bus_type") == 1 and item.get("usage_page") == 0xFF00
            and item.get("usage") == 2 and item.get("path")
        }
        self.known = {path: slots for path, slots in self.known.items() if path in active}
        for path, item in active.items():
            if scan or path not in self.known:
                found = self.probe(path, item)
                self.known.setdefault(path, {}).update(found)
        return [device for slots in self.known.values() for device in slots.values()]

    def probe(self, path, item):
        found = {}
        receiver = RECEIVERS[item["product_id"]]
        identity = item.get("serial_number") or path.hex()
        handle = hid.device()
        try:
            handle.open_path(path)
            for slot in range(1, 7):
                if read_percentage(handle, slot) is None:
                    continue
                name, kind = describe(handle, slot, receiver)
                icon_id = uuid5(NAMESPACE_URL, f"peripheral-battery-tray/hidpp/{item['product_id']}/{identity}/{slot}/{name}")
                found[slot] = Peripheral(name, kind, icon_id, path, slot)
        except OSError:
            pass
        finally:
            handle.close()
        return found
