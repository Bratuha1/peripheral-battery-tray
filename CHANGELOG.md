# Changelog

## 1.0.0

- Added independent USB and Bluetooth searches and experimental discovery of precise HID++ 2.0 battery readings on selected Logitech USB receivers.
- Added a choice between device silhouettes and battery indicators, plus a shortcut to Windows tray visibility settings.
- Enabled per-user startup on first launch. Windows sign-in starts the app in the tray.

- Added a Windows settings window in English and Russian, with system, light and dark themes.
- Added background discovery and polling, reading timestamps, connection status and per-device visibility.
- Added separate or combined Windows tray icons, optional percentage badges and configurable low-charge alerts.
- Added per-user startup, minimized launch, autosave, reset and local rotating logs.
- Preserved the IPI and Logitech USB readers and the standard Bluetooth LE Battery Service. Moved USB protocols into a profile registry.
- Added one-file Windows packaging, portable ZIP, optional per-user installer, checksums, and GitHub Actions builds and draft releases.
- Added automated regression tests. See the release checklist for hardware validation.
