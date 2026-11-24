"""Smoke test the frozen EXE in an isolated AppData directory on Windows."""

import argparse
import ctypes
from ctypes import wintypes as wt
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from windows import SHOW_MESSAGE, WINDOW_CLASS, bind, user


def wait_until(predicate, description, seconds=20):
    end = monotonic() + seconds
    while monotonic() < end:
        if result := predicate():
            return result
        sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {description}")


def check_pe(path):
    with path.open("rb") as handle:
        handle.seek(0x3C)
        header, = struct.unpack("<I", handle.read(4))
        handle.seek(header)
        if handle.read(6) != b"PE\0\0\x64\x86":
            raise ValueError("Expected a Windows x64 PE executable")
        handle.seek(header + 24 + 68)
        if handle.read(2) != b"\x02\x00":
            raise ValueError("Expected a Windows GUI subsystem executable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("--lifecycle", action="store_true", help="test the GUI on an interactive Windows desktop")
    path = parser.parse_args()
    exe = path.exe.resolve(strict=True)
    check_pe(exe)
    find = bind(user, "FindWindowW", wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
    visible = bind(user, "IsWindowVisible", wt.BOOL, wt.HWND)
    post = bind(user, "PostMessageW", wt.BOOL, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
    if find(WINDOW_CLASS, None):
        raise RuntimeError("Exit the running app before its lifecycle test.")

    with TemporaryDirectory() as temp:
        appdata = Path(temp) / "PeripheralBatteryTray"
        appdata.mkdir()
        settings = appdata / "settings.json"
        settings.write_text(json.dumps({"language": "en", "start_minimized": True}), encoding="utf-8")
        env = {**os.environ, "APPDATA": temp}
        result = subprocess.run([str(exe), "--version"], env=env, timeout=30)
        if result.returncode:
            raise RuntimeError(f"Packaged EXE returned {result.returncode} for --version")
        result = subprocess.run([str(exe), "--check", "--config", str(appdata / "missing.toml")],
                                env=env, timeout=30)
        if result.returncode != 2:
            raise RuntimeError(f"Packaged CLI did not return expected config error: {result.returncode}")
        print("PASS: x64, console-free PE and packaged CLI")

        if not path.lifecycle:
            return
        process = subprocess.Popen([str(exe)], env=env)
        try:
            native = wait_until(lambda: find(WINDOW_CLASS, None), "native message window")
            title = lambda: find("TkTopLevel", "Peripheral Battery Tray")
            tk_window = wait_until(title, "Tk window")
            if visible(tk_window):
                raise RuntimeError("Startup window should be hidden")
            second = subprocess.run([str(exe), "--show"], env=env, timeout=30)
            if second.returncode:
                raise RuntimeError(f"Second launch returned {second.returncode}")
            wait_until(lambda: visible(tk_window), "activation by the second instance")
            post(tk_window, 0x0010, 0, 0)
            wait_until(lambda: not visible(tk_window), "close to tray")
            post(native, SHOW_MESSAGE, 0, 0)
            wait_until(lambda: visible(tk_window), "reactivated settings")
            log_path = appdata / "app.log"
            post(native, 0x0218, 0x0012, 0)
            wait_until(lambda: "System resumed; refreshing devices" in log_path.read_text(encoding="utf-8"),
                       "refresh after synthetic resume")
            post(native, 0x0016, 1, 0)
            if process.wait(timeout=15):
                raise RuntimeError(f"Packaged application exited with {process.returncode}")
            log = log_path.read_text(encoding="utf-8")
            if log.count("started") != 1 or "Application stopped" not in log or "ERROR" in log:
                raise RuntimeError(f"Unexpected lifecycle log:\n{log}")
            print("PASS: minimized startup, single instance, close to tray, synthetic resume and clean exit")
        finally:
            # Terminate only the dedicated PyInstaller process tree from this test.
            if process.poll() is None:
                subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                               check=True, capture_output=True, timeout=10)
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
