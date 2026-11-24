# v1.0.0 manual release checklist

Start with clean x64 Windows 10 and Windows 11 accounts and the exact artifacts intended for release. Record the OS build, EXE SHA-256, connection mode, model and firmware version for each result.

- Start the portable app without Python installed. Install and uninstall for a standard user. Verify Start menu launch, no console, settings preservation and removal of the matching startup entry.
- Test IPI Haze X Pro (`372E:10F9`) and Logitech G PRO X 2 LIGHTSPEED (`046D:0AF7`). Compare several readings against the vendor utility, including charging, sleep, receiver unplug/replug and headset power-off. Check that an unavailable battery is shown with a dash.
- Test a BLE device that advertises Battery Service and one with a manually configured address. Confirm discovery, a successful uncached read, shutdown/reconnect behavior and recovery from disabled Bluetooth.
- Switch between separate and combined tray icons and test charge badges and tooltips at 100%, 0% and intermediate battery levels where hardware permits. Test visibility toggling and an empty list.
- Move icons out of the overflow area. Restart Explorer, sign out/in and reboot without moving the executable. Record which icons Windows retains and where.
- Test alerts below the configured threshold, sustained low charge, temporary disconnect and recovery above the rearm point. Check Windows Do Not Disturb behavior.
- Put the PC to sleep and resume with each transport in use. Verify a refresh after resume, settings responsiveness while scanning and no extra app window after launching twice.
- Test both languages, all themes, an OS theme change, high DPI scaling, Windows sign-in startup and minimized launch. Confirm settings persistence and reset.
- Measure CPU, process count and private RAM after initialization, over several polling cycles and after repeated disconnects/resumes.

Leave the GitHub release in draft until the hardware results are reviewed.
