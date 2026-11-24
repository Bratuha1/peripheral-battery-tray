# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "peripheral_battery.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "assets" / "battery.ico"), "assets"),
        (str(root / "LICENSE"), "."),
        (str(root / "build" / "licenses"), "licenses"),
    ],
    hiddenimports=["bleak.backends.winrt.client", "bleak.backends.winrt.scanner"],
    excludes=["numpy", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="PeripheralBatteryTray",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / "assets" / "battery.ico"),
    version=str(root / "build" / "version.txt"),
)
