"""
ui/log_viewer.py
─────────────────
Floating Toplevel window that shows live log output,
polled from the shared gui_log_queue every 150 ms.

Features
────────
- Colour-coded by level  (DEBUG=grey, INFO=green, WARN=yellow,
                          ERROR=red, CRITICAL=magenta)
- Search / filter bar
- Auto-scroll toggle
- Export current session to a new .log file
- Clear display
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog
import queue
from utils.logger import gui_log_queue, get_log_file_path
from utils.config import BG_DARK, BG_PANEL, ACCENT, TEXT_LIGHT

# ── Level → colour tag ────────────────────────────────────────────────────────
_LEVEL_COLOURS = {
    "DEBUG":    "#6a6a8a",
    "INFO":     "#55cc77",
    "WARNING":  "#e0b84a",
    "ERROR":    "#e05555",
    "CRITICAL": "#cc55cc",
}
_DEFAULT_FG = "#b0b0c0"


class LogViewer(tk.Toplevel):
    """
    Stand-alone floating log window.  Create once, hide/show as needed.

    Usage
    -----
    viewer = LogViewer(root)
    viewer.withdraw()          # start hidden
    viewer.deiconify()         # show
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("📋  Application Log Viewer")
        self.geometry("900x480")
        self.minsize(700, 320)
        self.configure(bg=BG_DARK)

        self._auto_scroll = tk.BooleanVar(value=True)
        self._filter_var  = tk.StringVar()
        self._level_var   = tk.StringVar(value="ALL")
        self._paused      = False
        self._pause_var   = tk.BooleanVar(value=False)

        self._all_lines: list = []     # raw store for re-filtering

        self._build()
        self._poll()                   # start polling queue

        # Don't destroy — just hide
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        bar = tk.Frame(self, bg=BG_PANEL, height=40)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        def tbtn(text, cmd, color=ACCENT):
            b = tk.Button(
                bar, text=text, command=cmd,
                bg=color, fg="white", relief=tk.FLAT,
                padx=10, font=("Consolas", 8, "bold"), cursor="hand2",
            )
            b.pack(side=tk.LEFT, padx=3, pady=5)
            return b

        tbtn("🗑  Clear",        self._clear_display,  "#5a3a3a")
        tbtn("📂  Open Log File", self._open_log_file, "#3a5a3a")
        tbtn("💾  Export",        self._export,        "#3a4a5a")

        tk.Checkbutton(
            bar, text="Auto-scroll", variable=self._auto_scroll,
            bg=BG_PANEL, fg=TEXT_LIGHT, selectcolor=BG_DARK,
            font=("Consolas", 8), activebackground=BG_PANEL,
            activeforeground=TEXT_LIGHT,
        ).pack(side=tk.LEFT, padx=6)

        tk.Checkbutton(
            bar, text="Pause",
            variable=self._pause_var,
            command=self._toggle_pause,
            bg=BG_PANEL, fg=TEXT_LIGHT, selectcolor=BG_DARK,
            font=("Consolas", 8), activebackground=BG_PANEL,
            activeforeground=TEXT_LIGHT,
        ).pack(side=tk.LEFT, padx=2)

        # Level filter
        tk.Label(
            bar, text="  Level:",
            bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 8),
        ).pack(side=tk.LEFT, padx=(10, 2))

        level_combo = ttk.Combobox(
            bar, textvariable=self._level_var,
            values=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            font=("Consolas", 8), width=9, state="readonly",
        )
        level_combo.pack(side=tk.LEFT)
        level_combo.bind("<<ComboboxSelected>>", lambda _: self._refilter())

        # Search
        tk.Label(
            bar, text="  Search:",
            bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 8),
        ).pack(side=tk.LEFT, padx=(10, 2))

        tk.Entry(
            bar, textvariable=self._filter_var,
            bg=BG_DARK, fg=TEXT_LIGHT,
            insertbackground=TEXT_LIGHT, relief=tk.FLAT,
            font=("Consolas", 8), width=22,
        ).pack(side=tk.LEFT, ipady=3)

        self._filter_var.trace_add("write", lambda *_: self._refilter())

        # Log file path label
        self._file_label = tk.Label(
            bar,
            text=f"  {get_log_file_path()}",
            bg=BG_PANEL, fg="#666688",
            font=("Consolas", 7),
        )
        self._file_label.pack(side=tk.RIGHT, padx=8)

        # ── Text area ─────────────────────────────────────────────────────────
        text_frame = tk.Frame(self, bg=BG_DARK)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))

        v_scroll = tk.Scrollbar(text_frame)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        h_scroll = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.text = tk.Text(
            text_frame,
            bg="#0b0b18", fg=_DEFAULT_FG,
            font=("Consolas", 8),
            relief=tk.FLAT, bd=0,
            state=tk.DISABLED,
            wrap=tk.NONE,
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set,
        )
        self.text.pack(fill=tk.BOTH, expand=True)
        v_scroll.config(command=self.text.yview)
        h_scroll.config(command=self.text.xview)

        # Configure colour tags
        for level, colour in _LEVEL_COLOURS.items():
            self.text.tag_config(level, foreground=colour)
        self.text.tag_config("HIGHLIGHT", background="#3a3a10")

        # ── Status bar ────────────────────────────────────────────────────────
        self._count_var = tk.StringVar(value="0 lines")
        status = tk.Frame(self, bg=BG_PANEL, height=22)
        status.pack(fill=tk.X, side=tk.BOTTOM)
        status.pack_propagate(False)
        tk.Label(
            status, textvariable=self._count_var,
            bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 8),
        ).pack(side=tk.LEFT, padx=8)

    # ── polling ───────────────────────────────────────────────────────────────
    def _poll(self):
        """Pull up to 50 lines per tick from the shared queue."""
        if not self._paused:
            try:
                for _ in range(50):
                    line = gui_log_queue.get_nowait()
                    self._all_lines.append(line)
                    if self._passes_filter(line):
                        self._append_line(line)
            except queue.Empty:
                pass
        self.after(150, self._poll)

    # ── rendering ─────────────────────────────────────────────────────────────
    def _append_line(self, line: str):
        tag   = self._level_tag(line)
        query = self._filter_var.get().strip().lower()

        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, line + "\n", tag)

        # Highlight search term
        if query:
            start = "1.0"
            while True:
                pos = self.text.search(query, start, stopindex=tk.END,
                                       nocase=True)
                if not pos:
                    break
                end   = f"{pos}+{len(query)}c"
                self.text.tag_add("HIGHLIGHT", pos, end)
                start = end

        self.text.config(state=tk.DISABLED)

        if self._auto_scroll.get():
            self.text.see(tk.END)

        # Update line count
        shown = int(self.text.index(tk.END).split(".")[0]) - 1
        self._count_var.set(
            f"{len(self._all_lines)} total | {shown} shown"
        )

    # ── filter helpers ────────────────────────────────────────────────────────
    def _passes_filter(self, line: str) -> bool:
        level_ok = (
            self._level_var.get() == "ALL"
            or f"| {self._level_var.get()}" in line
        )
        query   = self._filter_var.get().strip().lower()
        text_ok = not query or query in line.lower()
        return level_ok and text_ok

    def _refilter(self):
        """Redraw text area applying current level + search filters."""
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)
        for line in self._all_lines:
            if self._passes_filter(line):
                self._append_line(line)

    @staticmethod
    def _level_tag(line: str) -> str:
        for lvl in ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"):
            if f"| {lvl}" in line:
                return lvl
        return ""

    # ── actions ───────────────────────────────────────────────────────────────
    def _clear_display(self):
        self._all_lines.clear()
        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.config(state=tk.DISABLED)
        self._count_var.set("0 lines")

    def _toggle_pause(self):
        self._paused = self._pause_var.get()

    def _open_log_file(self):
        """Open today's log file in the default text editor."""
        import subprocess
        import platform
        path = get_log_file_path()
        if not os.path.exists(path):
            return
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])

    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text", "*.txt")],
            initialfile="exported_session.log",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self._all_lines))