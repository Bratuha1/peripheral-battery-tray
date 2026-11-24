"""Native Windows notification area. All shell operations run on the UI thread."""

import ctypes
from ctypes import wintypes as wt
from dataclasses import dataclass
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid5
import sys

from visuals import APP_ICON, render_icon
from windows import SHOW_MESSAGE, WINDOW_CLASS, bind, kernel, user

TRAY_MESSAGE = 0x8002
APP_ID = UUID("c3589602-2eda-4497-a1aa-52e77778e25f")
NIM_ADD, NIM_MODIFY, NIM_DELETE, NIM_SETFOCUS, NIM_SETVERSION = range(5)
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO, NIF_GUID, NIF_SHOWTIP = 1, 2, 4, 16, 32, 128
WM_CONTEXTMENU, WM_POWERBROADCAST, WM_SETTINGCHANGE = 0x007B, 0x0218, 0x001A
WM_ENDSESSION = 0x0016
PBT_APMRESUMEAUTOMATIC = 0x0012
NIN_SELECT, NIN_KEYSELECT = 0x0400, 0x0401
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WindowClass(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT), ("proc", WNDPROC), ("class_extra", ctypes.c_int),
        ("window_extra", ctypes.c_int), ("instance", wt.HINSTANCE), ("icon", wt.HICON),
        ("cursor", wt.HANDLE), ("background", wt.HBRUSH), ("menu", wt.LPCWSTR),
        ("name", wt.LPCWSTR),
    ]


class NotifyData(ctypes.Structure):
    _fields_ = [
        ("size", wt.DWORD), ("window", wt.HWND), ("id", wt.UINT), ("flags", wt.UINT),
        ("callback", wt.UINT), ("icon", wt.HICON), ("tip", wt.WCHAR * 128),
        ("state", wt.DWORD), ("state_mask", wt.DWORD), ("info", wt.WCHAR * 256),
        ("version", wt.UINT), ("info_title", wt.WCHAR * 64), ("info_flags", wt.DWORD),
        ("guid", ctypes.c_ubyte * 16), ("balloon_icon", wt.HICON),
    ]


notify_icon = bind(ctypes.WinDLL("shell32"), "Shell_NotifyIconW", wt.BOOL,
                   wt.DWORD, ctypes.POINTER(NotifyData))
default_proc = bind(user, "DefWindowProcW", ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
destroy_window = bind(user, "DestroyWindow", wt.BOOL, wt.HWND)
load_icon = bind(user, "LoadImageW", wt.HANDLE, wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                 ctypes.c_int, ctypes.c_int, wt.UINT)
destroy_icon = bind(user, "DestroyIcon", wt.BOOL, wt.HICON)


def truncate(text, limit):
    # The shell limits UTF-16 code units, including supplementary characters.
    return text.encode("utf-16-le")[:limit * 2].decode("utf-16-le", errors="ignore")


@dataclass(frozen=True)
class IconSpec:
    title: str
    kind: str
    level: int | None = None
    threshold: int = 15
    percent: bool = False

    @property
    def drawing(self):
        return self.kind, self.level, self.threshold, self.percent


@dataclass
class TrayEntry:
    number: int
    guid: UUID
    spec: IconSpec
    handle: int
    registered: bool = False

    def send(self, window, operation, flags=0, **kwargs):
        return notify_icon(operation, ctypes.byref(NotifyData(
            size=ctypes.sizeof(NotifyData), window=window, id=self.number,
            flags=flags | NIF_GUID, guid=(ctypes.c_ubyte * 16).from_buffer_copy(self.guid.bytes_le),
            **kwargs,
        )))

    def register(self, window):
        self.registered = bool(self.send(
            window, NIM_ADD, NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP,
            callback=TRAY_MESSAGE, icon=self.handle, tip=truncate(self.spec.title, 127),
        ))
        if self.registered and not self.send(window, NIM_SETVERSION, version=4):
            logging.warning("Could not set tray icon behavior version")


class Tray:
    def __init__(self, dispatch, menu):
        self.dispatch = dispatch
        self.menu = menu
        self.entries = {}
        self.next_number = 1
        executable = sys.executable if getattr(sys, "frozen", False) else __file__
        self.path = str(Path(executable).resolve()).casefold()
        self.taskbar_created = bind(user, "RegisterWindowMessageW", wt.UINT, wt.LPCWSTR)("TaskbarCreated")
        self.proc = WNDPROC(self.window_proc)
        self.instance = bind(kernel, "GetModuleHandleW", wt.HMODULE, wt.LPCWSTR)(None)
        self.unregister = bind(user, "UnregisterClassW", wt.BOOL, wt.LPCWSTR, wt.HINSTANCE)
        register = bind(user, "RegisterClassW", wt.ATOM, ctypes.POINTER(WindowClass))
        if not register(ctypes.byref(WindowClass(proc=self.proc, instance=self.instance, name=WINDOW_CLASS))):
            raise ctypes.WinError(ctypes.get_last_error())
        create = bind(user, "CreateWindowExW", wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR,
                      wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                      wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID)
        self.window = create(0, WINDOW_CLASS, None, 0x80000000, 0, 0, 0, 0,
                             None, None, self.instance, None)
        if not self.window:
            error = ctypes.get_last_error()
            self.unregister(WINDOW_CLASS, self.instance)
            raise ctypes.WinError(error)

    def window_proc(self, window, message, wparam, lparam):
        try:
            if message == TRAY_MESSAGE:
                event = lparam & 0xFFFF
                if event == WM_CONTEXTMENU:
                    self.popup(window, (lparam >> 16) & 0xFFFF, wparam)
                elif event in (NIN_SELECT, NIN_KEYSELECT):
                    self.dispatch("show")
                return 0
            if message == SHOW_MESSAGE:
                self.dispatch("show")
                return 0
            if message == self.taskbar_created:
                for entry in self.entries.values():
                    entry.register(window)
                return 0
            if message == WM_POWERBROADCAST and wparam == PBT_APMRESUMEAUTOMATIC:
                self.dispatch("resume")
                return 1
            if message == WM_ENDSESSION and wparam:
                self.dispatch("exit")
                return 0
            if message == WM_SETTINGCHANGE:
                self.dispatch("theme")
        except Exception:
            logging.exception("Windows tray message failed")
        return default_proc(window, message, wparam, lparam)

    def popup(self, window, number, coordinates):
        create = bind(user, "CreatePopupMenu", wt.HMENU)
        append = bind(user, "AppendMenuW", wt.BOOL, wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR)
        foreground = bind(user, "SetForegroundWindow", wt.BOOL, wt.HWND)
        track = bind(user, "TrackPopupMenu", wt.UINT, wt.HMENU, wt.UINT, ctypes.c_int,
                     ctypes.c_int, ctypes.c_int, wt.HWND, ctypes.c_void_p)
        destroy = bind(user, "DestroyMenu", wt.BOOL, wt.HMENU)
        post = bind(user, "PostMessageW", wt.BOOL, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        menu = create()
        if not menu:
            return
        items = self.menu()
        try:
            for index, (label, _) in enumerate(items, 1):
                append(menu, 0, index, label)
            x = ctypes.c_short(coordinates & 0xFFFF).value
            y = ctypes.c_short((coordinates >> 16) & 0xFFFF).value
            foreground(window)
            index = track(menu, 0x010A, x, y, 0, window, None)
            if index:
                self.dispatch(items[index - 1][1])
            post(window, 0, 0, 0)
        finally:
            destroy(menu)
            for entry in self.entries.values():
                if entry.number == number:
                    entry.send(window, NIM_SETFOCUS)
                    break

    def make_handle(self, spec):
        if spec.kind == "app":
            handle = load_icon(None, str(APP_ICON), 1, 32, 32, 0x10)
        else:
            with TemporaryDirectory() as directory:
                path = Path(directory) / "tray.ico"
                render_icon(*spec.drawing).save(path)
                handle = load_icon(None, str(path), 1, 32, 32, 0x10)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def sync(self, desired):
        for guid in self.entries.keys() - desired.keys():
            self.remove(guid)
        for guid, spec in desired.items():
            entry = self.entries.get(guid)
            if entry is None:
                entry = TrayEntry(self.next_number, guid, spec, self.make_handle(spec))
                self.entries[guid] = entry
                self.next_number = self.next_number % 65535 + 1
                entry.register(self.window)
                if not entry.registered:
                    # Windows ties an existing GUID to the executable path.
                    entry.guid = uuid5(guid, self.path)
                    entry.register(self.window)
            elif entry.spec != spec:
                flags, args = NIF_TIP | NIF_SHOWTIP, {"tip": truncate(spec.title, 127)}
                old_handle = None
                if entry.spec.drawing != spec.drawing:
                    handle = self.make_handle(spec)
                    old_handle, entry.handle = entry.handle, handle
                    flags |= NIF_ICON
                    args["icon"] = entry.handle
                entry.spec = spec
                if entry.registered:
                    entry.registered = bool(entry.send(self.window, NIM_MODIFY, flags, **args))
                if old_handle:
                    destroy_icon(old_handle)
            if not entry.registered:
                entry.register(self.window)
        return any(entry.registered for entry in self.entries.values())

    def notify(self, title, text):
        for entry in self.entries.values():
            if entry.registered:
                return entry.send(
                    self.window, NIM_MODIFY, NIF_INFO, info=truncate(text, 255),
                    info_title=truncate(title, 63), info_flags=0x81,
                )
        return False

    def remove(self, guid):
        entry = self.entries.pop(guid)
        if entry.registered:
            entry.send(self.window, NIM_DELETE)
        destroy_icon(entry.handle)

    def close(self):
        for guid in list(self.entries):
            self.remove(guid)
        destroy_window(self.window)
        self.unregister(WINDOW_CLASS, self.instance)
