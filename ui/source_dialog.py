"""
ui/source_dialog.py
────────────────────
Fixed modal dialog — click a source card to immediately browse & load.
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from core.youtube_downloader import YouTubeDownloader
from utils.config import BG_DARK, BG_PANEL, ACCENT, TEXT_LIGHT
from utils.logger import get_logger

log = get_logger("ui.SourceDialog")


class SourceDialog(tk.Toplevel):
    """
    result dict after closing:
        {"type": "video"|"image"|"image_folder"|"youtube", "path": "..."}
    or None if cancelled.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Open Annotation Source")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)
        self.geometry("580x500")
        self.grab_set()
        self.focus_set()

        self.result: Optional[dict] = None
        self._downloader: Optional[YouTubeDownloader] = None
        self._selected_path = tk.StringVar(value="")
        self._selected_type = tk.StringVar(value="")

        self._build()
        self.wait_window()

    # ─────────────────────────────────────────────────────────────────────────
    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill=tk.X, padx=24, pady=(20, 0))

        tk.Label(hdr, text="Choose Annotation Source",
                 bg=BG_DARK, fg=ACCENT,
                 font=("Consolas", 14, "bold")).pack(anchor=tk.W)
        tk.Label(hdr, text="Click a card to browse, then press Open",
                 bg=BG_DARK, fg="#777799",
                 font=("Consolas", 9)).pack(anchor=tk.W, pady=(2, 0))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=20, pady=12)

        # Notebook
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Src.TNotebook",
                        background=BG_DARK, borderwidth=0)
        style.configure("Src.TNotebook.Tab",
                        background=BG_PANEL, foreground=TEXT_LIGHT,
                        font=("Consolas", 9, "bold"), padding=[14, 6])
        style.map("Src.TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])

        self._nb = ttk.Notebook(self, style="Src.TNotebook")
        self._nb.pack(fill=tk.BOTH, expand=True, padx=16)

        local_tab = tk.Frame(self._nb, bg=BG_DARK)
        yt_tab    = tk.Frame(self._nb, bg=BG_DARK)
        self._nb.add(local_tab, text="  📁  Local File / Folder  ")
        self._nb.add(yt_tab,    text="  ▶  YouTube / URL  ")
        self._nb.bind("<<NotebookTabChanged>>",
                      lambda _e: self._on_tab_switch())

        self._build_local_tab(local_tab)
        self._build_youtube_tab(yt_tab)

        # Path preview bar
        preview = tk.Frame(self, bg=BG_PANEL, height=28)
        preview.pack(fill=tk.X, padx=16, pady=(8, 0))
        preview.pack_propagate(False)
        tk.Label(preview, text=" Selected: ",
                 bg=BG_PANEL, fg="#666688",
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        tk.Label(preview, textvariable=self._selected_path,
                 bg=BG_PANEL, fg=ACCENT,
                 font=("Consolas", 8),
                 anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=16, pady=8)

        # Bottom buttons
        btns = tk.Frame(self, bg=BG_DARK)
        btns.pack(pady=(0, 14), padx=16, fill=tk.X)

        tk.Button(btns, text="✖  Cancel",
                  command=self.destroy,
                  bg="#444455", fg="white", relief=tk.FLAT,
                  padx=18, pady=8,
                  font=("Consolas", 10, "bold"),
                  cursor="hand2").pack(side=tk.LEFT, padx=(0, 8))

        self._open_btn = tk.Button(
            btns, text="Open  →",
            command=self._confirm,
            bg=ACCENT, fg="white", relief=tk.FLAT,
            padx=18, pady=8,
            font=("Consolas", 10, "bold"),
            cursor="hand2",
        )
        self._open_btn.pack(side=tk.LEFT)

        self._status_lbl = tk.Label(
            btns, text="",
            bg=BG_DARK, fg="#aaaacc",
            font=("Consolas", 8))
        self._status_lbl.pack(side=tk.RIGHT, padx=8)

    # ── Local tab ─────────────────────────────────────────────────────────────
    def _build_local_tab(self, parent):
        cards = [
            ("video",        "🎬", "Video File",
             "MP4 · AVI · MOV · MKV · WEBM", "#4a3a8a"),
            ("image",        "🖼", "Single Image",
             "JPG · PNG · BMP · TIFF · WEBP", "#3a6a4a"),
            ("image_folder", "📂", "Image Folder",
             "Load every image inside a folder", "#3a4a7a"),
        ]
        for src_type, icon, title, sub, hover_bg in cards:
            self._make_card(parent, src_type, icon, title, sub, hover_bg)

    def _make_card(self, parent, src_type, icon, title, subtitle, hover_bg):
        """Clickable card that opens browse dialog immediately."""

        card = tk.Frame(parent, bg=BG_PANEL, cursor="hand2",
                        relief=tk.FLAT, bd=0)
        card.pack(fill=tk.X, padx=14, pady=5, ipady=4)

        # Colour indicator strip
        strip = tk.Frame(card, bg=hover_bg, width=5)
        strip.pack(side=tk.LEFT, fill=tk.Y)

        body = tk.Frame(card, bg=BG_PANEL)
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=8)

        # Radio indicator
        self._rb_var = getattr(self, "_rb_var", None) or tk.StringVar(value="")
        rb = tk.Radiobutton(body,
                            variable=self._selected_type,
                            value=src_type,
                            bg=BG_PANEL,
                            activebackground=BG_PANEL,
                            selectcolor=hover_bg)
        rb.pack(side=tk.LEFT)

        text_frame = tk.Frame(body, bg=BG_PANEL)
        text_frame.pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(text_frame,
                 text=f"{icon}  {title}",
                 bg=BG_PANEL, fg=TEXT_LIGHT,
                 font=("Consolas", 10, "bold")).pack(anchor=tk.W)
        tk.Label(text_frame,
                 text=subtitle,
                 bg=BG_PANEL, fg="#777799",
                 font=("Consolas", 8)).pack(anchor=tk.W)

        browse_btn = tk.Button(
            body,
            text="Browse…",
            command=lambda t=src_type: self._browse(t),
            bg=hover_bg, fg="white", relief=tk.FLAT,
            padx=10, pady=4,
            font=("Consolas", 8, "bold"),
            cursor="hand2",
        )
        browse_btn.pack(side=tk.RIGHT, padx=4)

        # Clicking anywhere on the card triggers browse
        for widget in (card, body, strip, text_frame):
            widget.bind("<Button-1>",
                        lambda _e, t=src_type: self._browse(t))

        # Hover highlight
        def _enter(_e):
            card.config(bg=hover_bg)
            body.config(bg=hover_bg)
            text_frame.config(bg=hover_bg)
            strip.config(bg=ACCENT)

        def _leave(_e):
            card.config(bg=BG_PANEL)
            body.config(bg=BG_PANEL)
            text_frame.config(bg=BG_PANEL)
            strip.config(bg=hover_bg)

        for widget in (card, body, strip, text_frame):
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)

    def _browse(self, src_type: str):
        """Open the OS file picker for the given type and store the result."""
        self._selected_type.set(src_type)

        if src_type == "image_folder":
            path = filedialog.askdirectory(
                title="Select Image Folder",
                parent=self,
            )
        elif src_type == "image":
            path = filedialog.askopenfilename(
                title="Select Image",
                parent=self,
                filetypes=[
                    ("Image files",
                     "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
                    ("All files", "*.*"),
                ],
            )
        else:  # video
            path = filedialog.askopenfilename(
                title="Select Video File",
                parent=self,
                filetypes=[
                    ("Video files",
                     "*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv"),
                    ("All files", "*.*"),
                ],
            )

        if path:
            self._selected_path.set(path)
            log.info(f"User browsed — type={src_type}, path={path}")
            self._status_lbl.config(
                text=f"✔  {os.path.basename(path)}", fg="#55cc77")
        else:
            # User cancelled the file dialog — do nothing
            if not self._selected_path.get():
                self._selected_type.set("")

    # ── YouTube tab ───────────────────────────────────────────────────────────
    def _build_youtube_tab(self, parent):
        pad = {"padx": 16}

        tk.Label(parent, text="Paste a YouTube or video URL:",
                 bg=BG_DARK, fg=TEXT_LIGHT,
                 font=("Consolas", 9)).pack(
            pady=(16, 4), anchor=tk.W, **pad)

        url_row = tk.Frame(parent, bg=BG_DARK)
        url_row.pack(fill=tk.X, **pad)

        self._yt_url_var = tk.StringVar()
        self._url_entry  = tk.Entry(
            url_row, textvariable=self._yt_url_var,
            bg=BG_PANEL, fg=TEXT_LIGHT,
            insertbackground=TEXT_LIGHT,
            relief=tk.FLAT, font=("Consolas", 9),
        )
        self._url_entry.pack(side=tk.LEFT, fill=tk.X,
                             expand=True, ipady=6, padx=(0, 8))
        self._url_entry.bind("<Return>", lambda _e: self._fetch_yt_info())

        tk.Button(url_row, text="ℹ  Info",
                  command=self._fetch_yt_info,
                  bg="#555566", fg="white", relief=tk.FLAT,
                  padx=10, font=("Consolas", 9), cursor="hand2",
                  ).pack(side=tk.LEFT)

        # Info card
        info_card = tk.Frame(parent, bg=BG_PANEL)
        info_card.pack(fill=tk.X, pady=10, **pad)

        self._yt_title_var   = tk.StringVar(value="Title:    —")
        self._yt_channel_var = tk.StringVar(value="Channel:  —")
        self._yt_dur_var     = tk.StringVar(value="Duration: —")

        for var in (self._yt_title_var,
                    self._yt_channel_var,
                    self._yt_dur_var):
            tk.Label(info_card, textvariable=var,
                     bg=BG_PANEL, fg=TEXT_LIGHT,
                     font=("Consolas", 8), anchor=tk.W,
                     ).pack(fill=tk.X, padx=10, pady=3)

        # Quality selector
        q_row = tk.Frame(parent, bg=BG_DARK)
        q_row.pack(fill=tk.X, **pad, pady=(4, 0))

        tk.Label(q_row, text="Quality:",
                 bg=BG_DARK, fg=TEXT_LIGHT,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=(0, 8))

        self._quality_var = tk.StringVar(value="720")
        for q, label in [("360", "360p"), ("480", "480p"),
                         ("720", "720p ★"), ("1080", "1080p"),
                         ("best", "Best")]:
            tk.Radiobutton(
                q_row, text=label,
                variable=self._quality_var, value=q,
                bg=BG_DARK, fg=TEXT_LIGHT,
                selectcolor=BG_PANEL,
                activebackground=BG_DARK,
                font=("Consolas", 8),
            ).pack(side=tk.LEFT, padx=4)

        # Progress section
        prog_outer = tk.Frame(parent, bg=BG_DARK)
        prog_outer.pack(fill=tk.X, pady=10, **pad)

        self._yt_status_var = tk.StringVar(value="")
        tk.Label(prog_outer, textvariable=self._yt_status_var,
                 bg=BG_DARK, fg="#aaaacc",
                 font=("Consolas", 8)).pack(anchor=tk.W, pady=(0, 4))

        self._yt_progress = ttk.Progressbar(
            prog_outer, mode="determinate", maximum=100)
        self._yt_progress.pack(fill=tk.X)
        self._yt_progress["value"] = 0

        # Download button
        self._dl_btn = tk.Button(
            parent, text="⬇  Download & Open",
            command=self._start_yt_download,
            bg="#cc3333", fg="white", relief=tk.FLAT,
            padx=14, pady=8,
            font=("Consolas", 10, "bold"),
            cursor="hand2",
        )
        self._dl_btn.pack(pady=8, **pad, anchor=tk.W)

    def _fetch_yt_info(self):
        url = self._yt_url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL",
                                   "Please paste a YouTube URL.", parent=self)
            return
        self._yt_status_var.set("⏳  Fetching info…")
        self._url_entry.config(state=tk.DISABLED)

        def _work():
            dl   = YouTubeDownloader(url)
            info = dl.get_video_info()
            self.after(0, lambda: self._show_yt_info(info))

        threading.Thread(target=_work, daemon=True).start()

    def _show_yt_info(self, info: dict):
        self._url_entry.config(state=tk.NORMAL)
        if not info:
            self._yt_status_var.set("⚠  Could not fetch info. Check the URL.")
            return
        dur = info.get("duration", 0)
        m, s = divmod(int(dur), 60)
        h, m = divmod(m, 60)
        dur_str = (f"{h:02d}:{m:02d}:{s:02d}"
                   if h else f"{m:02d}:{s:02d}")
        title = info.get("title", "?")[:55]
        self._yt_title_var.set(f"Title:    {title}")
        self._yt_channel_var.set(f"Channel:  {info.get('channel','?')}")
        self._yt_dur_var.set(f"Duration: {dur_str}")
        self._yt_status_var.set("✔  Info loaded. Press Download & Open.")

    def _start_yt_download(self):
        url = self._yt_url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL",
                                   "Please paste a YouTube URL.", parent=self)
            return
        quality = self._quality_var.get()
        self._dl_btn.config(state=tk.DISABLED, text="Downloading…")
        self._yt_status_var.set("Starting download…")
        self._yt_progress["value"] = 0
        log.info(f"YouTube download — url={url}, quality={quality}")

        def _progress(pct, speed, eta):
            self.after(0, lambda: (
                self._yt_progress.__setitem__("value", pct),
                self._yt_status_var.set(
                    f"⬇  {pct:.1f}%  |  {speed}  |  ETA {eta}")
            ))

        def _done(path):
            self.after(0, lambda: self._yt_done(path))

        def _error(msg):
            self.after(0, lambda: self._yt_error(msg))

        self._downloader = YouTubeDownloader(
            url=url, quality=quality,
            progress_callback=_progress,
            done_callback=_done,
            error_callback=_error,
        )
        self._downloader.start()

    def _yt_done(self, path: str):
        self._yt_progress["value"] = 100
        self._yt_status_var.set(f"✔  Done!  →  {os.path.basename(path)}")
        self._selected_path.set(path)
        self._selected_type.set("youtube")
        log.info(f"YouTube downloaded → {path}")
        self.result = {"type": "youtube", "path": path}
        self.after(1000, self.destroy)

    def _yt_error(self, msg: str):
        self._dl_btn.config(state=tk.NORMAL,
                            text="⬇  Download & Open")
        self._yt_status_var.set(f"✘  {msg}")
        messagebox.showerror("Download Error", msg, parent=self)

    # ── tab switch ────────────────────────────────────────────────────────────
    def _on_tab_switch(self):
        tab = self._nb.index(self._nb.select())
        if tab == 0:
            self._open_btn.config(text="Open  →", state=tk.NORMAL)
        else:
            # YouTube tab handles itself via Download button
            self._open_btn.config(text="Open  →", state=tk.DISABLED)

    # ── confirm (local) ───────────────────────────────────────────────────────
    def _confirm(self):
        path = self._selected_path.get().strip()
        src  = self._selected_type.get().strip()

        if not path:
            messagebox.showwarning(
                "Nothing selected",
                "Please click a card and browse for a file or folder.",
                parent=self,
            )
            return

        if not os.path.exists(path):
            messagebox.showerror(
                "Path not found",
                f"The selected path does not exist:\n{path}",
                parent=self,
            )
            return

        # Validate type matches path
        if src == "image_folder" and not os.path.isdir(path):
            messagebox.showerror("Wrong type",
                                 "Selected path is not a folder.",
                                 parent=self)
            return
        if src in ("video", "image") and not os.path.isfile(path):
            messagebox.showerror("Wrong type",
                                 "Selected path is not a file.",
                                 parent=self)
            return

        self.result = {"type": src, "path": path}
        log.info(f"Source confirmed — type={src}, path={path}")
        self.destroy()