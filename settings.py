"""Persistent, validated settings and a local rotating diagnostic log."""

from dataclasses import asdict, dataclass, field
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

APP_NAME = "Peripheral Battery Tray"
VERSION = "1.0.0"
APP_DATA = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "PeripheralBatteryTray"
MIN_INTERVAL, MAX_INTERVAL = 5, 3600


@dataclass
class Settings:
    autostart: bool = True
    start_minimized: bool = False
    interval: int = 20
    mouse_threshold: int = 15
    headset_threshold: int = 15
    other_threshold: int = 15
    show_percent: bool = False
    tray_mode: str = "separate"
    icon_style: str = "device"
    theme: str = "system"
    language: str = "system"
    hidden: list[str] = field(default_factory=list)
    bluetooth: dict[str, str] = field(default_factory=dict)

    def threshold(self, kind):
        return {
            "mouse": self.mouse_threshold,
            "headset": self.headset_threshold,
        }.get(kind, self.other_threshold)


def load_settings(path):
    defaults = Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defaults
    except (OSError, ValueError):
        logging.exception("Could not load settings")
        return defaults
    if not isinstance(raw, dict):
        logging.warning("Settings must contain a JSON object")
        return defaults

    for key in ("autostart", "start_minimized", "show_percent"):
        if type(raw.get(key)) is bool:
            setattr(defaults, key, raw[key])
    for key, choices in {
        "tray_mode": ("separate", "combined"),
        "icon_style": ("device", "battery"),
        "theme": ("light", "dark", "system"),
        "language": ("en", "ru", "system"),
    }.items():
        if raw.get(key) in choices:
            setattr(defaults, key, raw[key])
    for key, bounds in {
        "interval": (MIN_INTERVAL, MAX_INTERVAL),
        "mouse_threshold": (0, 100),
        "headset_threshold": (0, 100),
        "other_threshold": (0, 100),
    }.items():
        value = raw.get(key)
        if type(value) is int and bounds[0] <= value <= bounds[1]:
            setattr(defaults, key, value)
    if isinstance(raw.get("hidden"), list):
        for value in raw["hidden"]:
            try:
                device_id = str(UUID(value)) if isinstance(value, str) else None
            except ValueError:
                continue
            if device_id and device_id not in defaults.hidden:
                defaults.hidden.append(device_id)
    if isinstance(raw.get("bluetooth"), dict):
        from devices import BLUETOOTH_ADDRESS

        defaults.bluetooth = {
            address.upper(): name.strip()[:85]
            for address, name in raw["bluetooth"].items()
            if BLUETOOTH_ADDRESS.fullmatch(address.upper())
            and isinstance(name, str)
        }
    return defaults


def save_settings(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temp = Path(handle.name)
            json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temp.replace(path)
    finally:
        if temp:
            temp.unlink(missing_ok=True)


def configure_logging(directory):
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "app.log", maxBytes=262_144, backupCount=2, encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[handler],
    )
