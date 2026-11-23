# Peripheral Battery Tray

A small Windows utility that shows the charge of wireless mice and headsets in the notification area. Hover over an icon to see the percentage. The icon turns red below 15% and gray when a reading is unavailable. Right-click for **Refresh battery** or **Exit**. The app runs locally.

[Инструкция на русском](docs/ru.md) · [Add a device](docs/adding-devices.md)

## Compatibility

| Device or protocol | Connection | Status |
| --- | --- | --- |
| IPI Haze X Pro | 2.4 GHz USB receiver, `372E:10F9` | Tested on hardware |
| Logitech G PRO X 2 LIGHTSPEED | LIGHTSPEED USB receiver, `046D:0AF7` | Tested on hardware |
| Mice and headsets with a readable BLE Battery Level characteristic | Bluetooth LE Battery Service, `180F` / `2A19` | Configurable. Device compatibility varies |

2.4 GHz receivers can use a different protocol for each model. Classic Bluetooth-only headsets, proprietary USB receivers without a profile, and separate readings for individual earbuds and cases are outside the current support.

## Run on Windows

Use Windows 10 or 11 and 64-bit Python 3.13. The USB profiles were verified on Windows 11. This version runs from source. You can clone the repository with Git or choose **Code → Download ZIP**, extract it, and open PowerShell in the extracted folder.

```powershell
git clone https://github.com/Bratuha1/peripheral-battery-tray.git
cd peripheral-battery-tray
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe peripheral_battery.py --check
.\.venv\Scripts\python.exe peripheral_battery.py
```

The built-in USB profiles appear when their receivers are present. If Windows puts the icons under **^**, drag them into the visible tray. To run without a console, start the same script with `.\.venv\Scripts\pythonw.exe`.

### Add a Bluetooth device

1. Connect it in Windows Bluetooth settings and keep it awake.
2. Run `.\.venv\Scripts\python.exe peripheral_battery.py --scan-ble` and find the device address.
3. Copy `devices.example.toml` to `devices.toml`. Set the name, address, and icon type (`mouse` or `headset`).
4. Run `--check` again. When a percentage appears, restart the tray app to add the icon.

The [device guide](docs/adding-devices.md) covers troubleshooting and adding USB profiles.

### Troubleshooting

| What you see | What to try |
| --- | --- |
| `py` is missing or cannot find Python 3.13 | Install 64-bit [Python 3.13 for Windows](https://www.python.org/downloads/windows/), make sure the launcher is available, and reopen PowerShell. |
| `No supported device found` | Plug in the original USB receiver or add the BLE device to `devices.toml`. Use `--list-hid` or `--scan-ble` to identify it. |
| The icon is gray or shows `Battery unavailable` | Wake the device, check its connection, and choose **Refresh battery**. Then repeat `--check` if needed. |
| The icon is missing although `--check` works | Start the app without `--check`, leave it running, and look under **^** beside the clock. |

For a bug or compatibility request, follow the [reporting checklist](docs/adding-devices.md#report-a-bug-or-request-a-device).

## Development

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Contributions with an exact model, connection mode, and hardware-verified readings are welcome.

[MIT License](LICENSE)
