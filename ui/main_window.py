"""Root application frame — supports video, image, image-folder & YouTube."""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from core.video_loader          import VideoLoader
from core.frame_extractor       import FrameExtractor
from core.image_loader          import ImageLoader
from core.image_frame_extractor import ImageFrameExtractor
from core.yolo_annotator        import YOLOAnnotator
from core.annotation_manager   import AnnotationManager
from models.annotation_model   import BoundingBox
from storage.frame_storage      import FrameStorage
from storage.label_storage      import LabelStorage
from ui.video_player            import VideoPlayer
from ui.annotation_panel        import AnnotationPanel
from ui.log_viewer              import LogViewer
from ui.source_dialog           import SourceDialog
from utils.logger               import get_logger
from utils.config               import BG_DARK, BG_PANEL, ACCENT, TEXT_LIGHT

log = get_logger("ui.MainWindow")

_SOURCE_LABELS = {
    "video":        "🎬 Video",
    "image":        "🖼 Image",
    "image_folder": "📂 Image Folder",
    "youtube":      "▶ YouTube",
}

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


def _find_images_recursive(folder: str):
    """
    Scan folder AND all subfolders for supported image files.
    Returns sorted list of absolute paths.
    """
    found = []
    for root, dirs, files in os.walk(folder):
        # Sort dirs so traversal is deterministic
        dirs.sort()
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS:
                found.append(os.path.join(root, f))
    return found


class MainWindow(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_DARK)
        self.manager: AnnotationManager | None = None
        self._busy        = False
        self._log_viewer  = None
        self._source_type = None
        self._build_ui()
        log.info("MainWindow initialised")

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_toolbar()

        content = tk.Frame(self, bg=BG_DARK)
        content.pack(fill=tk.BOTH, expand=True)

        self.player = VideoPlayer(
            content,
            on_frame_change=self._on_frame_change,
            on_box_drawn=self._on_box_drawn,
        )
        self.player.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                         padx=6, pady=6)

        self.ann_panel = AnnotationPanel(
            content,
            on_yolo_click     = self._run_yolo,
            on_yolo_all_click = self._run_yolo_all,
            on_save_click     = self._save,
            on_clear_click    = self._clear_frame,
            on_delete_box     = self._delete_box,
            on_conf_change    = self._on_conf_change,
        )
        self.ann_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=6)

        self._build_status()
        self._build_progress()

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        def btn(text, cmd, color=ACCENT):
            b = tk.Button(
                bar, text=text, command=cmd,
                bg=color, fg="white", relief=tk.FLAT,
                padx=12, pady=6, font=("Consolas", 9, "bold"),
                activebackground="#9d8fff", cursor="hand2",
            )
            b.pack(side=tk.LEFT, padx=3, pady=6)
            return b

        btn("📂  Open",       self._open_source)
        btn("🎬  Video",      self._open_video_direct)
        btn("🖼  Image",      self._open_image_direct)
        btn("▶  YouTube",    self._open_youtube_direct, color="#cc3333")
        btn("💾  Save",       self._save,               color="#2d7a4e")
        btn("⚡  YOLO Frame", self._run_yolo)
        btn("🔁  YOLO All",   self._run_yolo_all,       color="#5a4fbf")
        btn("📋  Logs",       self._show_logs,           color="#3a4a6a")

        self._source_badge = tk.Label(
            bar, text="  No source",
            bg=BG_PANEL, fg="#666688",
            font=("Consolas", 8, "italic"),
        )
        self._source_badge.pack(side=tk.RIGHT, padx=10)

    def _build_status(self):
        self.status_var = tk.StringVar(
            value="No source loaded. Click 📂 Open or choose a source type."
        )
        bar = tk.Frame(self, bg=BG_PANEL, height=26)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        tk.Label(
            bar, textvariable=self.status_var,
            bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 9),
        ).pack(side=tk.LEFT, padx=10)

    def _build_progress(self):
        from tkinter import ttk
        pf = tk.Frame(self, bg=BG_PANEL, height=6)
        pf.pack(fill=tk.X, side=tk.BOTTOM)
        pf.pack_propagate(False)
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "App.Horizontal.TProgressbar",
            troughcolor=BG_PANEL, background=ACCENT, thickness=6,
        )
        self._progress = ttk.Progressbar(
            pf, mode="indeterminate",
            style="App.Horizontal.TProgressbar",
        )
        self._progress_visible = False

    # ── progress ──────────────────────────────────────────────────────────────
    def _show_progress(self):
        if not self._progress_visible:
            self._progress.pack(fill=tk.X)
            self._progress.start(12)
            self._progress_visible = True

    def _hide_progress(self):
        if self._progress_visible:
            self._progress.stop()
            self._progress.pack_forget()
            self._progress_visible = False

    def _run_in_thread(self, task_fn, done_fn=None, error_fn=None):
        self._busy = True
        self._show_progress()

        def _worker():
            try:
                result = task_fn()
                if done_fn:
                    self.after(0, lambda r=result: done_fn(r))
            except Exception as exc:
                # FIX: Python 3.13 lambda scoping bug — capture exc explicitly
                _exc = exc
                log.error(f"Background task error: {_exc}", exc_info=True)
                if error_fn:
                    self.after(0, lambda e=_exc: error_fn(e))
                else:
                    self.after(
                        0, lambda e=_exc: messagebox.showerror("Error", str(e))
                    )
            finally:
                self.after(0, self._task_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _task_done(self):
        self._busy = False
        self._hide_progress()

    # ── open source actions ───────────────────────────────────────────────────
    def _open_source(self):
        """Unified tabbed source dialog."""
        if self._busy:
            return
        dlg = SourceDialog(self.master)
        if dlg.result:
            self._load_from_result(dlg.result)

    def _open_video_direct(self):
        """Quick-open a video file."""
        if self._busy:
            return
        path = filedialog.askopenfilename(
            title="Open Video",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.webm *.flv"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._load_from_result({"type": "video", "path": path})

    def _open_image_direct(self):
        """Quick-open a single image or image folder."""
        if self._busy:
            return

        win = tk.Toplevel(self.master)
        win.title("Open Image")
        win.configure(bg=BG_DARK)
        win.resizable(False, False)
        win.grab_set()
        win.focus_set()

        result = {"type": None, "path": None}

        tk.Label(
            win, text="What do you want to open?",
            bg=BG_DARK, fg=TEXT_LIGHT,
            font=("Consolas", 11, "bold"),
        ).pack(pady=(20, 10), padx=24)

        def _pick_image():
            path = filedialog.askopenfilename(
                title="Select Image", parent=win,
                filetypes=[
                    ("Image files",
                     "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
                    ("All files", "*.*"),
                ],
            )
            if path:
                result["type"] = "image"
                result["path"] = path
                win.destroy()

        def _pick_folder():
            path = filedialog.askdirectory(
                title="Select Image Folder", parent=win
            )
            if path:
                result["type"] = "image_folder"
                result["path"] = path
                win.destroy()

        btn_cfg = dict(
            bg=ACCENT, fg="white", relief=tk.FLAT,
            padx=20, pady=10,
            font=("Consolas", 10, "bold"),
            cursor="hand2",
        )
        tk.Button(win, text="🖼   Single Image",
                  command=_pick_image, **btn_cfg).pack(
            fill=tk.X, padx=24, pady=4)
        tk.Button(win, text="📂   Image Folder",
                  command=_pick_folder, **btn_cfg).pack(
            fill=tk.X, padx=24, pady=4)
        tk.Button(win, text="Cancel",
                  command=win.destroy,
                  bg="#444455", fg="white", relief=tk.FLAT,
                  padx=20, pady=8,
                  font=("Consolas", 9),
                  cursor="hand2").pack(pady=(4, 16), padx=24, fill=tk.X)

        win.wait_window()

        if result["path"]:
            self._load_from_result(result)

    def _open_youtube_direct(self):
        """Open the source dialog directly on the YouTube tab."""
        if self._busy:
            return
        dlg = SourceDialog(self.master)
        if dlg.result:
            self._load_from_result(dlg.result)

    # ── unified loader dispatcher ─────────────────────────────────────────────
    def _load_from_result(self, result: dict):
        src_type = result["type"]
        path     = result["path"]
        self._source_type = src_type
        self._update_badge(src_type)
        log.info(f"Loading source — type={src_type}, path={path}")

        if src_type in ("video", "youtube"):
            self._load_video(path)
        elif src_type in ("image", "image_folder"):
            self._load_images(path)

    # ── video loader ──────────────────────────────────────────────────────────
    def _load_video(self, path: str):
        self._set_status(f"Opening video: {os.path.basename(path)}…")

        def _work():
            loader    = VideoLoader(path)
            loader.open()
            extractor = FrameExtractor(loader, step=1, save_frames=True)
            yolo      = YOLOAnnotator()
            yolo.load()
            vname = os.path.splitext(os.path.basename(path))[0]
            mgr   = AnnotationManager(
                loader, extractor, yolo,
                FrameStorage(vname),
                LabelStorage(vname),
            )
            self.after(0, lambda: self._set_status("Extracting frames…"))
            mgr.load_video()
            mgr.load_existing_labels()
            return mgr

        def _done(mgr: AnnotationManager):
            self.manager = mgr
            self.player.load(mgr.loader, mgr.all_frame_indices())
            self._set_status(
                f"Video loaded — '{os.path.basename(path)}'  "
                f"| {mgr.loader.total_frames} frames "
                f"| {mgr.loader.fps:.0f} fps"
            )

        def _err(exc):
            messagebox.showerror("Video Load Error", str(exc))
            self._set_status("Failed to load video.")

        self._run_in_thread(_work, _done, _err)

    # ── image loader ──────────────────────────────────────────────────────────
    def _load_images(self, path: str):
        is_folder = os.path.isdir(path)
        label     = "folder" if is_folder else "image"
        self._set_status(f"Loading {label}: {os.path.basename(path)}…")
        log.info(f"Loading images — is_folder={is_folder}, path={path}")

        def _work():
            # ── FIX: if folder has no images at root, scan subfolders ─────────
            if is_folder:
                all_images = _find_images_recursive(path)
                if not all_images:
                    raise FileNotFoundError(
                        f"No images found in folder or subfolders:\n{path}\n\n"
                        f"Supported formats: JPG, PNG, BMP, TIFF, WEBP\n\n"
                        f"Make sure your images are inside the selected folder."
                    )
                log.info(f"Found {len(all_images)} image(s) in: {path}")

            loader = ImageLoader(path)
            loader.open()

            if loader.total_frames == 0:
                raise ValueError(
                    "No supported images found.\n"
                    "Supported formats: JPG, PNG, BMP, TIFF, WEBP"
                )

            extractor = ImageFrameExtractor(loader, copy_files=True)
            yolo      = YOLOAnnotator()
            yolo.load()

            src_name = (
                os.path.basename(path.rstrip("/\\")) or "images"
            )
            # Sanitise name for use as directory
            src_name = "".join(
                c if c.isalnum() or c in "-_." else "_"
                for c in src_name
            )

            mgr = AnnotationManager(
                loader, extractor, yolo,
                FrameStorage(src_name),
                LabelStorage(src_name),
            )
            self.after(0, lambda: self._set_status(
                f"Processing {loader.total_frames} image(s)…"
            ))
            mgr.load_video()           # duck-typed — works for images too
            mgr.load_existing_labels()
            return mgr

        def _done(mgr: AnnotationManager):
            self.manager = mgr
            indices = mgr.all_frame_indices()
            self.player.load(mgr.loader, indices)
            noun = "images" if is_folder else "image"
            self._set_status(
                f"{'Folder' if is_folder else 'Image'} loaded — "
                f"'{os.path.basename(path)}'  |  {len(indices)} {noun}"
            )
            log.info(f"Image source ready — {len(indices)} item(s)")

        def _err(exc):
            log.error(f"Image load error: {exc}", exc_info=True)
            messagebox.showerror(
                "Image Load Error",
                f"Could not load:\n{path}\n\n{exc}",
            )
            self._set_status("Failed to load image source.")

        self._run_in_thread(_work, _done, _err)

    # ── frame change callback ─────────────────────────────────────────────────
    def _on_frame_change(self, frame_index: int, bgr_frame):
        if self.manager is None:
            return
        ann   = self.manager.get_annotation(frame_index)
        boxes = ann.boxes if ann else []
        self.player.set_overlay_boxes(boxes)
        self.ann_panel.update_boxes(boxes, self.manager.yolo.class_names)

    # ── manual box drawn ──────────────────────────────────────────────────────
    def _on_box_drawn(self, x1_n: float, y1_n: float,
                      x2_n: float, y2_n: float):
        if self.manager is None:
            return

        cls_name    = self.ann_panel.get_selected_class()
        class_names = self.manager.yolo.class_names
        cls_id      = next(
            (k for k, v in class_names.items()
             if v.lower() == cls_name.lower()), 0
        )

        box = BoundingBox(
            class_id   = cls_id,
            class_name = cls_name,
            x_center   = (x1_n + x2_n) / 2,
            y_center   = (y1_n + y2_n) / 2,
            width      = x2_n - x1_n,
            height     = y2_n - y1_n,
            confidence = 1.0,
        )

        idx = self.player.current_frame_index
        self.manager.add_box(idx, box)

        ann = self.manager.get_annotation(idx)
        self.player.set_overlay_boxes(ann.boxes)
        self.ann_panel.update_boxes(ann.boxes, self.manager.yolo.class_names)
        src_label = (
            "image" if self._source_type in ("image", "image_folder")
            else "frame"
        )
        self._set_status(
            f"Manual box added — '{cls_name}' on {src_label} {idx}. "
            f"Total: {len(ann.boxes)} box(es)."
        )

    # ── delete selected box ───────────────────────────────────────────────────
    def _delete_box(self, box_index: int):
        if not self._require_manager():
            return
        idx = self.player.current_frame_index
        self.manager.remove_box(idx, box_index)
        ann = self.manager.get_annotation(idx)
        self.player.set_overlay_boxes(ann.boxes)
        self.ann_panel.update_boxes(ann.boxes, self.manager.yolo.class_names)
        self._set_status(f"Deleted box [{box_index}] from index {idx}.")

    # ── confidence change ─────────────────────────────────────────────────────
    def _on_conf_change(self, val: float):
        if self.manager:
            self.manager.yolo.confidence = val
            log.debug(f"Confidence updated → {val:.2f}")

    # ── YOLO single frame ─────────────────────────────────────────────────────
    def _run_yolo(self):
        if not self._require_manager() or self._busy:
            return
        idx        = self.player.current_frame_index
        conf       = self.ann_panel.get_confidence_threshold()
        cls_filter = self.ann_panel.get_class_filter()
        self.manager.yolo.confidence = conf
        self._set_status(f"Running YOLO on index {idx}…")
        log.info(f"YOLO single — idx={idx}, conf={conf}, filter={cls_filter}")

        def _work():
            ann = self.manager.auto_annotate_frame(idx)
            if cls_filter:
                ann.boxes = [
                    b for b in ann.boxes
                    if b.class_name.lower() in cls_filter
                ]
                ann.is_annotated = bool(ann.boxes)
            return ann

        def _done(ann):
            self.player.set_overlay_boxes(ann.boxes)
            self.ann_panel.update_boxes(
                ann.boxes, self.manager.yolo.class_names
            )
            self._set_status(
                f"YOLO: {len(ann.boxes)} object(s) at index {idx}."
            )

        self._run_in_thread(_work, _done)

    # ── YOLO all frames ───────────────────────────────────────────────────────
    def _run_yolo_all(self):
        if not self._require_manager() or self._busy:
            return
        total      = self.manager.total_count
        conf       = self.ann_panel.get_confidence_threshold()
        cls_filter = self.ann_panel.get_class_filter()
        self.manager.yolo.confidence = conf
        self._set_status("Running YOLO on all…")
        log.info(f"YOLO all — conf={conf}, filter={cls_filter}")

        def _progress(done, tot):
            self.after(0, lambda d=done, t=tot: self._set_status(
                f"YOLO annotating… {d}/{t}"
            ))

        def _work():
            self.manager.auto_annotate_all(progress_callback=_progress)
            if cls_filter:
                for ann in self.manager._annotations.values():
                    ann.boxes = [
                        b for b in ann.boxes
                        if b.class_name.lower() in cls_filter
                    ]
                    ann.is_annotated = bool(ann.boxes)
            return self.manager.annotated_count

        def _done(count):
            self._set_status(
                f"YOLO complete — {count}/{total} annotated."
            )

        self._run_in_thread(_work, _done)

    # ── save annotations ──────────────────────────────────────────────────────
    def _save(self):
        if not self._require_manager() or self._busy:
            return
        self._set_status("Saving annotations…")

        def _work():
            self.manager.save_annotations()
            return self.manager.annotated_count

        def _done(count):
            self._set_status(f"Saved {count} annotation file(s).")

        self._run_in_thread(_work, _done)

    # ── clear current frame ───────────────────────────────────────────────────
    def _clear_frame(self):
        if not self._require_manager():
            return
        idx = self.player.current_frame_index
        self.manager.clear_frame(idx)
        self.player.set_overlay_boxes([])
        self.ann_panel.update_boxes([], {})
        self._set_status(f"Cleared annotations for index {idx}.")

    # ── log viewer ────────────────────────────────────────────────────────────
    def _show_logs(self):
        if self._log_viewer is None or not self._log_viewer.winfo_exists():
            self._log_viewer = LogViewer(self.master)
            log.info("Log viewer opened")
        else:
            self._log_viewer.deiconify()
            self._log_viewer.lift()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _require_manager(self) -> bool:
        if self.manager is None:
            messagebox.showinfo("No source",
                                "Please open a source first.")
            return False
        return True

    def _set_status(self, msg: str):
        self.status_var.set(msg)
        log.info(f"[STATUS] {msg}")
        self.update_idletasks()

    def _update_badge(self, src_type: str):
        label = _SOURCE_LABELS.get(src_type, src_type)
        self._source_badge.config(text=f"  Source: {label}  ")

    def on_close(self):
        log.info("Application closing — releasing resources")
        if self.manager:
            self.manager.loader.release()
        self.master.destroy()