"""Windows startup registration, locale and single-instance activation."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes as wt
from pathlib import Path
import subprocess
import sys
import winreg

WINDOW_CLASS = "PeripheralBatteryTrayWindow"
SHOW_MESSAGE = 0x8001
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "PeripheralBatteryTray"

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
user = ctypes.WinDLL("user32", use_last_error=True)


def bind(library, name, result, *parameters):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = parameters
    return function


@contextmanager
def single_instance():
    create = bind(kernel, "CreateMutexW", wt.HANDLE, wt.LPVOID, wt.BOOL, wt.LPCWSTR)
    close = bind(kernel, "CloseHandle", wt.BOOL, wt.HANDLE)
    handle = create(None, False, r"Local\PeripheralBatteryTray.Desktop")
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    try:
        yield error != 183
    finally:
        close(handle)


def activate_instance():
    find = bind(user, "FindWindowW", wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
    post = bind(user, "PostMessageW", wt.BOOL, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
    if window := find(WINDOW_CLASS, None):
        post(window, SHOW_MESSAGE, 0, 0)


def startup_command():
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        command = [str(executable)]
    else:
        pythonw = executable.with_name("pythonw.exe")
        command = [str(pythonw if pythonw.is_file() else executable),
                   str(Path(__file__).with_name("peripheral_battery.py"))]
    return subprocess.list2cmdline([*command, "--autostart"])


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, kind = winreg.QueryValueEx(key, RUN_NAME)
    except FileNotFoundError:
        return False
    return kind == winreg.REG_SZ and value.casefold() == startup_command().casefold()


def set_autostart(enabled):
    if enabled:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, RUN_NAME)
        except FileNotFoundError:
            pass


def system_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def system_language():
    lang_id = bind(kernel, "GetUserDefaultUILanguage", wt.WORD)()
    return "ru" if lang_id & 0x03FF == 0x19 else "en"
