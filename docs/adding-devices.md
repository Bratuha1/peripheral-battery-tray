# Add a device

Start with the connection mode. A USB receiver, a cable and Bluetooth can expose different battery protocols for the same peripheral.

## Bluetooth LE Battery Service

Pair the device in Windows if it requires pairing, wake it and click **Find Bluetooth**. The scan discovers devices advertising `180F` and only saves a device when an uncached read of the `2A19` Battery Level characteristic returns a valid value between 0 and 100. Auto-discovered devices use the generic battery icon.

To try a device that exposes the service without advertising it, use the source CLI to get the device address and edit `%APPDATA%\PeripheralBatteryTray\devices.toml`. Copy [devices.example.toml](../devices.example.toml) or add the entry directly. Restart the app.

```toml
[[bluetooth]]
name = "My wireless headset"
kind = "headset"
address = "AA:BB:CC:DD:EE:FF"
```

Supported kinds are `mouse`, `headset` and `other`. Explicit `--config PATH` takes precedence. If an AppData config is absent, the app also accepts the legacy location beside the script or EXE. BLE devices with rotating addresses or missing advertisements can appear unavailable or as separate devices.

Run diagnostics from a source checkout with the project dependencies installed.

```powershell
.\.venv\Scripts\python.exe peripheral_battery.py --list-hid
.\.venv\Scripts\python.exe peripheral_battery.py --scan-ble
.\.venv\Scripts\python.exe peripheral_battery.py --check
```

See [Microsoft's BLE battery profile guidance](https://learn.microsoft.com/en-us/windows-hardware/design/accessory-guidelines/bluetooth-accessory-guidelines/bluetooth-accessory-guidelines-battery-profiles-services).

## USB receivers

Choose **Find USB** to scan the original USB profiles and Logitech USB receivers. This scan does not require a Bluetooth adapter. For selected Bolt, Unifying and LIGHTSPEED receivers the app discovers HID++ 2.0 feature `0x1004` and accepts a percentage only when the device advertises state-of-charge support and returns a valid value. Voltage and coarse charge categories are excluded. Compatibility with additional models is experimental pending hardware testing. See the [receiver IDs in Solaar](https://github.com/pwr-Solaar/Solaar/blob/master/lib/logitech_receiver/base_usb.py) and [Unified Battery implementation in Linux](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-hidpp.c).

### Add a USB profile to the source

1. Run `--list-hid` before and after connecting the receiver. Record its VID:PID and vendor usage page and usage. Matching a vendor ID alone can select an unrelated collection.
2. Find the exact model's protocol. Confirm the read command, report lengths and IDs, expected reply and unplugged or loading states against documentation and a physical device.
3. Add a module to [profiles](../profiles). Expose a `UsbProfile` with a stable UUID and a reader that accepts matching HID paths. Register it in [profiles/__init__.py](../profiles/__init__.py). The application, window, tray and polling code remain independent of the model.
4. Reuse the transport only when the report framing matches. Bound reads, always close the handle, and return a verified percentage or `None`. Preserve sample reports for parser tests.
5. Compare `--check` against a vendor reading across charge levels and disconnect/reconnect. Document the exact connection and test result. Each USB profile represents one device model.

The existing IPI profile follows the [IPI HUBX web driver](https://qbz.ipigame.cn/). The Logitech receiver uses Centurion framing. See the [PROX2-AutoSwitch diagnostic](https://github.com/Ayerdi/PROX2-AutoSwitch/blob/main/lib/LogitechProX2Centurion.psm1).

## Additional models reviewed for v1.0.0

| Vendor | Protocol evidence | What remains to qualify a profile |
| --- | --- | --- |
| Logitech | Vendor-authored [HID++ 2.0 specification](https://lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf) and [Solaar feature implementations](https://github.com/pwr-Solaar/Solaar/blob/master/docs/features.md). | Pick an exact model and receiver, identify the battery feature and verify whether it supplies a true percentage on Windows. |
| Razer | [OpenRazer](https://github.com/openrazer/openrazer) contains model-specific battery operations and identifiers. | Confirm the correct Windows HID collection, read transport and response for the model. |
| SteelSeries | [rivalcfg](https://github.com/flozz/rivalcfg) and [HeadsetControl](https://github.com/Sapd/HeadsetControl) contain model-specific mouse and headset readers. | Confirm receiver and firmware variants and verify whether the response contains an exact percentage. |
| Corsair | [HeadsetControl](https://github.com/Sapd/HeadsetControl) has separate implementations for models including VOID and Virtuoso. | Check the model, Windows interfaces, report framing and disconnected-state markers. |
| HyperX | [HeadsetControl](https://github.com/Sapd/HeadsetControl) has implementations for selected wireless headsets. | Verify receiver revision, transport and output scale for a specific headset. |

Protocol references identify candidates for follow-up. The experimental receiver scan qualifies devices dynamically by exact percentage support. Model-specific support requires physical validation.

## Report a bug or request a model

In a [GitHub issue](https://github.com/Bratuha1/peripheral-battery-tray/issues/new), include the exact model, connection mode, Windows version and reproduction steps. For USB, include VID:PID and vendor usage. Share the result of `--check` if relevant. Remove Bluetooth addresses and serial numbers from shared details.
