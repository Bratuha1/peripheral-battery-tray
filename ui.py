"""Lightweight Tk settings window styled for Windows."""

import ctypes
from ctypes import wintypes as wt
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import ImageTk

from settings import APP_NAME, MAX_INTERVAL, MIN_INTERVAL, VERSION
from visuals import APP_ICON, battery_color, render_icon
from windows import bind, system_dark, user

LIGHT = {
    "background": "#f4f6fa", "panel": "#ffffff", "field": "#f5f7fb",
    "text": "#182336", "muted": "#495974", "line": "#dfe5ef",
    "accent": "#1453b8", "hover": "#164594", "track": "#e4e9f3",
}
DARK = {
    "background": "#151a22", "panel": "#202733", "field": "#283246",
    "text": "#f1f5fc", "muted": "#afbdd4", "line": "#364257",
    "accent": "#255ebd", "hover": "#3370d2", "track": "#364257",
}


class SettingsWindow:
    def __init__(self, root, app):
        self.root, self.app = root, app
        self.page = "devices"
        self.images = []
        self.show_hidden = False
        self.root.title(APP_NAME)
        self.root.geometry("780x675")
        self.root.minsize(610, 470)
        self.root.iconbitmap(str(APP_ICON))
        self.root.protocol("WM_DELETE_WINDOW", app.hide_window)
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.palette = {}
        self.rebuild()

    def t(self, key):
        return self.app.t(key)

    def is_dark(self):
        theme = self.app.settings.theme
        return theme == "dark" or (theme == "system" and system_dark())

    def apply_palette(self):
        self.dark = self.is_dark()
        self.palette = DARK if self.dark else LIGHT
        p = self.palette
        self.root.configure(bg=p["background"])
        self.root.option_add("*TCombobox*Listbox.background", p["panel"])
        self.root.option_add("*TCombobox*Listbox.foreground", p["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.style.configure(".", font=("Segoe UI", 10), foreground=p["text"],
                             background=p["background"])
        for name, background in (("TButton", p["panel"]), ("Accent.TButton", p["accent"])):
            self.style.configure(name, padding=(13, 7), background=background,
                                 bordercolor=p["line"], lightcolor=background, darkcolor=background,
                                 foreground="#ffffff" if name.startswith("Accent") else p["text"])
            self.style.map(name, background=[("active", p["hover"] if name.startswith("Accent") else p["field"])])
        for name, background in (("TCheckbutton", p["background"]), ("Panel.TCheckbutton", p["panel"])):
            self.style.configure(name, background=background, indicatorbackground=p["field"],
                                 indicatorforeground=p["text"])
            self.style.map(name, background=[("active", background)])
        self.style.configure("Vertical.TScrollbar", background=p["field"], troughcolor=p["track"],
                             bordercolor=p["line"], lightcolor=p["line"], darkcolor=p["line"],
                             arrowcolor=p["muted"])
        for name in ("TCombobox", "TSpinbox"):
            self.style.configure(name, fieldbackground=p["panel"], foreground=p["text"],
                                 arrowcolor=p["text"], bordercolor=p["line"],
                                 lightcolor=p["line"], darkcolor=p["line"], padding=5)
            self.style.map(name, fieldbackground=[("readonly", p["panel"])],
                           foreground=[("readonly", p["text"])])
        self.root.update_idletasks()
        get_parent = bind(user, "GetParent", wt.HWND, wt.HWND)
        frame = get_parent(self.root.winfo_id())
        if frame:
            attribute = bind(ctypes.WinDLL("dwmapi"), "DwmSetWindowAttribute", ctypes.c_long,
                             wt.HWND, wt.DWORD, wt.LPVOID, wt.DWORD)
            value = wt.BOOL(self.dark)
            attribute(frame, 20, ctypes.byref(value), ctypes.sizeof(value))
            for number, color in ((35, p["panel"]), (36, p["text"])):
                red, green, blue = bytes.fromhex(color[1:])
                value = wt.DWORD(red | green << 8 | blue << 16)
                attribute(frame, number, ctypes.byref(value), ctypes.sizeof(value))

    def label(self, parent, text, size=10, bold=False, muted=False, background=None):
        p = self.palette
        return tk.Label(parent, text=text, bg=background or p["background"],
                        fg=p["muted" if muted else "text"], anchor="w", justify="left",
                        font=("Segoe UI", size, "bold" if bold else "normal"))

    def switch_page(self, page):
        self.page = page
        self.rebuild()

    def rebuild(self):
        for child in self.root.winfo_children():
            child.destroy()
        self.images.clear()
        self.apply_palette()
        p = self.palette
        header = tk.Frame(self.root, bg=p["background"])
        header.pack(fill="x", padx=26, pady=(19, 12))
        self.label(header, APP_NAME, 11, bold=True).pack(side="left")
        self.label(header, f"v{VERSION}", 9, muted=True).pack(side="right")

        navigation = tk.Frame(self.root, bg=p["background"])
        navigation.pack(fill="x", padx=26)
        for page in ("devices", "settings"):
            ttk.Button(navigation, text=self.t(page),
                       style="Accent.TButton" if self.page == page else "TButton",
                       command=lambda page=page: self.switch_page(page)).pack(side="left", padx=(0, 8))

        title = tk.Frame(self.root, bg=p["background"])
        title.pack(fill="x", padx=26, pady=(19, 12))
        self.label(title, self.t(self.page), 23, bold=True).grid(row=0, column=0, sticky="w")
        self.label(title, self.t(f"{self.page}_sub"), muted=True).grid(row=1, column=0, sticky="w")
        title.columnconfigure(0, weight=1)
        if self.page == "devices":
            controls = tk.Frame(title, bg=p["background"])
            controls.grid(row=0, column=1, rowspan=2, sticky="e")
            self.scan_buttons = []
            for source, style in (("usb", "Accent.TButton"), ("ble", "TButton")):
                button = ttk.Button(controls, text=self.t(f"scan_{source}"), style=style,
                                    command=lambda source=source: self.app.request_poll(discover=source))
                button.pack(side="left", padx=(6, 0))
                self.scan_buttons.append(button)
            self.hidden_var = tk.BooleanVar(value=self.show_hidden)
            ttk.Checkbutton(self.root, text=self.t("show_hidden"), variable=self.hidden_var,
                            command=self.toggle_hidden).pack(anchor="w", padx=26, pady=(0, 6))

        self.status = self.label(self.root, "", 9, muted=True)
        self.status.pack(side="bottom", fill="x", padx=26, pady=(6, 12))
        holder = tk.Frame(self.root, bg=p["background"])
        holder.pack(fill="both", expand=True, padx=26)
        self.canvas = tk.Canvas(holder, bg=p["background"], highlightthickness=0, takefocus=0)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        scroll.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=p["background"])
        body_id = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(body_id, width=event.width))
        self.body.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.root.bind("<MouseWheel>", self.scroll)
        if self.page == "devices":
            self.render_devices()
        else:
            self.render_settings()
        self.set_status()

    def scroll(self, event):
        if isinstance(event.widget, (ttk.Combobox, ttk.Spinbox)):
            return
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def set_status(self):
        self.status.configure(text=self.t(self.app.status))
        if self.page == "devices":
            for button in self.scan_buttons:
                button.state(["disabled" if self.app.scanning else "!disabled"])

    def toggle_hidden(self):
        self.show_hidden = self.hidden_var.get()
        self.render_devices()

    def render_devices(self):
        if self.page != "devices":
            return
        view = self.canvas.yview()[0]
        for child in self.body.winfo_children():
            child.destroy()
        self.images.clear()
        p = self.palette
        hidden = self.app.settings.hidden
        readings = [(key, reading) for key, reading in self.app.readings.items()
                    if self.show_hidden or key not in hidden]
        if not readings:
            card = self.card(self.body)
            self.label(card, self.t("empty"), 13, bold=True, background=p["panel"]).pack(anchor="w")
            tip = self.label(card, self.t("empty_help"), muted=True, background=p["panel"])
            tip.configure(wraplength=480)
            tip.pack(anchor="w", pady=(4, 0))
            return

        for key, reading in readings:
            device, level = reading.device, reading.level
            threshold = self.app.settings.threshold(device.kind)
            card = self.card(self.body)
            card.columnconfigure(1, weight=1)
            photo = ImageTk.PhotoImage(render_icon(device.kind, level, threshold))
            self.images.append(photo)
            tk.Label(card, image=photo, bg=p["panel"]).grid(row=0, column=0, rowspan=2, padx=(0, 12))
            name = self.label(card, self.app.name(device), 12, bold=True, background=p["panel"])
            name.configure(wraplength=280)
            name.grid(row=0, column=1, sticky="w")
            date = reading.updated.strftime("%d.%m.%Y %H:%M:%S" if self.app.language == "ru"
                                            else "%Y-%m-%d %H:%M:%S") if reading.updated else "—"
            state = self.t(reading.status)
            if key in hidden:
                state += f" · {self.t('hidden')}"
            self.label(card, f"{state}\n{self.t('last')}  {date}", 9, muted=True,
                       background=p["panel"]).grid(row=1, column=1, sticky="w")
            percent = f"{level}%" if level is not None else "—"
            self.label(card, percent, 16, bold=True, background=p["panel"]).grid(row=0, column=2)
            bar = tk.Canvas(card, width=78, height=5, bg=p["track"], highlightthickness=0)
            bar.grid(row=1, column=2, padx=10)
            if level:
                bar.create_rectangle(0, 0, round(78 * level / 100), 5,
                                     width=0, fill=battery_color(level, threshold))
            ttk.Button(card, text=self.t("unhide" if key in hidden else "hide"),
                       command=lambda key=key: self.app.toggle_device(key)).grid(row=0, column=3, rowspan=2, padx=(8, 0))
        self.body.update_idletasks()
        self.canvas.yview_moveto(view)

    def card(self, parent):
        p = self.palette
        card = tk.Frame(parent, bg=p["panel"], padx=15, pady=12,
                        highlightthickness=1, highlightbackground=p["line"])
        card.pack(fill="x", pady=(0, 8), padx=(0, 5))
        return card

    def section(self, key):
        self.label(self.body, self.t(key), 11, bold=True).pack(anchor="w", pady=(3, 5))
        card = self.card(self.body)
        card.columnconfigure(0, weight=1)
        return card

    def render_settings(self):
        appearance = self.section("appearance")
        self.choice(appearance, 0, "theme", ("system", "light", "dark"))
        self.choice(appearance, 1, "language", ("system", "en", "ru"))
        behavior = self.section("behavior")
        for row, key in enumerate(("autostart", "start_minimized", "show_percent")):
            value = tk.BooleanVar(value=getattr(self.app.settings, key))
            ttk.Checkbutton(behavior, text=self.t(key), variable=value, style="Panel.TCheckbutton",
                            command=lambda key=key, value=value: self.app.change_checkbox(key, value)
                            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        self.choice(behavior, 3, "tray_mode", ("separate", "combined"))
        self.choice(behavior, 4, "icon_style", ("device", "battery"))
        self.number(behavior, 5, "interval", MIN_INTERVAL, MAX_INTERVAL)
        ttk.Button(behavior, text=self.t("pin_tray"), command=self.app.open_tray_settings
                   ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        thresholds = self.section("thresholds")
        self.label(thresholds, self.t("threshold_help"), 9, muted=True,
                   background=self.palette["panel"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        for row, key in enumerate(("mouse_threshold", "headset_threshold", "other_threshold"), 1):
            self.number(thresholds, row, key, 0, 100)
        buttons = tk.Frame(self.body, bg=self.palette["background"])
        buttons.pack(fill="x", pady=(2, 8))
        ttk.Button(buttons, text=self.t("log"), command=self.app.open_log).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text=self.t("reset"), command=self.confirm_reset).pack(side="left")

    def choice(self, parent, row, key, options):
        self.label(parent, self.t(key), background=self.palette["panel"]).grid(row=row, column=0, sticky="w")
        box = ttk.Combobox(parent, state="readonly", width=19, values=[self.t(option) for option in options])
        box.current(options.index(getattr(self.app.settings, key)))
        box.grid(row=row, column=1, sticky="e", pady=3)
        box.bind("<<ComboboxSelected>>", lambda _: self.app.change_settings(**{key: options[box.current()]}))

    def number(self, parent, row, key, minimum, maximum):
        self.label(parent, self.t(key), background=self.palette["panel"]).grid(row=row, column=0, sticky="w")
        value = tk.StringVar(value=getattr(self.app.settings, key))
        box = ttk.Spinbox(parent, from_=minimum, to=maximum, width=8, textvariable=value)
        box.grid(row=row, column=1, sticky="e", pady=3)

        def commit(_=None):
            try:
                number = int(value.get())
            except ValueError:
                number = getattr(self.app.settings, key)
            number = max(minimum, min(maximum, number))
            self.app.change_settings(**{key: number})
            value.set(str(getattr(self.app.settings, key)))

        box.configure(command=commit)
        box.bind("<Return>", commit)
        box.bind("<FocusOut>", commit)

    def confirm_reset(self):
        if messagebox.askyesno(APP_NAME, self.t("reset_confirm"), parent=self.root, icon="warning"):
            self.app.reset_settings()
