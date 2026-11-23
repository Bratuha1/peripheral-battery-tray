# Add a mouse or headset

Start with the connection mode in use. A device may use different protocols over Bluetooth, its 2.4 GHz receiver, and its charging cable.

## Bluetooth LE Battery Service

1. Pair or connect the device through Windows. Keep it awake during diagnosis.
2. Run `python peripheral_battery.py --scan-ble` in the project's virtual environment. Find its address in the results.
3. Add a `[[bluetooth]]` table to a local `devices.toml` next to the script.

   ```toml
   [[bluetooth]]
   name = "My wireless headset"
   kind = "headset"
   address = "AA:BB:CC:DD:EE:FF"
   ```

4. Run `python peripheral_battery.py --check`. Once a percentage is available, restart the tray app.

The reader connects to service `180F` and reads the one-byte Battery Level characteristic `2A19`. Valid levels range from 0 to 100. Sleep, rotating addresses, and devices that expose charge only through Classic Bluetooth or a proprietary service can prevent a reading. A device can expose a service without advertising it. See [Microsoft's battery profile guidance](https://learn.microsoft.com/en-us/windows-hardware/design/accessory-guidelines/bluetooth-accessory-guidelines/bluetooth-accessory-guidelines-battery-profiles-services).

## USB receivers

1. Run `python peripheral_battery.py --list-hid` before and after connecting the receiver. Record the new VID:PID and the vendor usage page and usage. Matching only a brand's VID can select an unrelated device.
2. Find the battery read operation in the vendor's documentation, its utility, or an existing driver. Confirm the report ID, length, expected response, and any disconnect or loading values. VID:PID alone cannot supply this information.
3. Add a reader and register a `UsbProfile` in [devices.py](../devices.py). Generate a unique icon ID with `python -c "import uuid; print(uuid.uuid4())"`. This example uses placeholder identifiers:

   ```python
   UsbProfile(
       "Brand Model", "mouse", UUID("4e83e7db-2337-4fc4-b8c7-ea3bcbb73b7c"),
       0x1234, 0xABCD, 0xFF01, 0x0001, read_brand_model,
   )
   ```

   The reader receives candidate HID paths as a tuple. Open the verified vendor collection and send only the known read request, if one is needed. Bound reads by a timeout, close the handle, and return a verified percentage or `None`. The IPI and Logitech profiles show a 64-byte output-report transport. Other report sizes or feature reports require their own transport code.
4. Use `--check` to compare several readings against the vendor utility. Verify disconnect, reconnect, and charging where possible. Each built-in profile currently exposes one icon per model.

## Report a bug or request a device

Open a [GitHub Issue](https://github.com/Bratuha1/peripheral-battery-tray/issues/new) with the Windows version, exact device model, connection mode, and the output of `--check`. For bugs, include the steps to reproduce the issue. For a USB compatibility request, include the VID:PID and vendor usage from `--list-hid`. Mention whether Windows or the vendor's utility can read the charge, and link to the utility if available. Remove serial numbers and Bluetooth addresses.

## Protocol references

- [IPI HUBX web driver](https://qbz.ipigame.cn/) for the BY-tech MouseUni device-status query and the zero/loading behavior.
- [PROX2-AutoSwitch's Centurion diagnostic](https://github.com/Ayerdi/PROX2-AutoSwitch/blob/main/lib/LogitechProX2Centurion.psm1) and [HaloBattery's protocol notes](https://github.com/HeyOkay/HaloBattery/blob/main/docs/protocols.md) for the Logitech receiver.
- [Bleak's Windows API](https://bleak.readthedocs.io/en/latest/backends/windows.html) for Bluetooth LE reads.
