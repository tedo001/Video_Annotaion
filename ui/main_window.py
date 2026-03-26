"""Root application frame — holds toolbar, video player, and side panel."""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.video_loader      import VideoLoader
from core.frame_extractor   import FrameExtractor
from core.yolo_annotator    import YOLOAnnotator
from core.annotation_manager import AnnotationManager
from storage.frame_storage  import FrameStorage
from storage.label_storage  import LabelStorage
from ui.video_player        import VideoPlayer
from ui.annotation_panel    import AnnotationPanel
from utils.config           import BG_DARK, BG_PANEL, ACCENT, TEXT_LIGHT


class MainWindow(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_DARK)
        self.manager: AnnotationManager | None = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_toolbar()
        content = tk.Frame(self, bg=BG_DARK)
        content.pack(fill=tk.BOTH, expand=True)

        self.player = VideoPlayer(content, on_frame_change=self._on_frame_change)
        self.player.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.ann_panel = AnnotationPanel(
            content,
            on_yolo_click    = self._run_yolo,
            on_yolo_all_click= self._run_yolo_all,
            on_save_click    = self._save,
            on_clear_click   = self._clear_frame,
        )
        self.ann_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=6)

        self._build_status()

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        def btn(text, cmd):
            b = tk.Button(
                bar, text=text, command=cmd,
                bg=ACCENT, fg="white", relief=tk.FLAT,
                padx=14, pady=6, font=("Consolas", 10, "bold"),
                activebackground="#9d8fff", cursor="hand2",
            )
            b.pack(side=tk.LEFT, padx=4, pady=6)
            return b

        btn("📂  Open Video", self._open_video)
        btn("💾  Save All",   self._save)
        btn("⚡  YOLO Frame", self._run_yolo)
        btn("🔁  YOLO All",   self._run_yolo_all)

    def _build_status(self):
        self.status_var = tk.StringVar(value="No video loaded.")
        bar = tk.Frame(self, bg=BG_PANEL, height=26)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        tk.Label(
            bar, textvariable=self.status_var,
            bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 9),
        ).pack(side=tk.LEFT, padx=10)

    # ── actions ───────────────────────────────────────────────────────────────
    def _open_video(self):
        path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"), ("All", "*.*")]
        )
        if not path:
            return
        try:
            loader    = VideoLoader(path)
            loader.open()
            extractor = FrameExtractor(loader, step=1, save_frames=True)
            yolo      = YOLOAnnotator()
            vname     = os.path.splitext(os.path.basename(path))[0]
            f_store   = FrameStorage(vname)
            l_store   = LabelStorage(vname)

            self.manager = AnnotationManager(loader, extractor, yolo, f_store, l_store)
            self._set_status("Extracting frames…")
            self.manager.load_video()
            self.manager.load_existing_labels()

            indices = self.manager.all_frame_indices()
            self.player.load(loader, indices)
            self._set_status(
                f"Loaded '{os.path.basename(path)}'  "
                f"| {loader.total_frames} frames | {loader.fps:.0f} fps"
            )
        except Exception as exc:
            messagebox.showerror("Open Error", str(exc))

    def _on_frame_change(self, frame_index: int, bgr_frame):
        if self.manager is None:
            return
        ann = self.manager.get_annotation(frame_index)
        if ann:
            self.player.set_overlay_boxes(ann.boxes)
            self.ann_panel.update_boxes(ann.boxes, self.manager.yolo.class_names)
        else:
            self.player.set_overlay_boxes([])
            self.ann_panel.update_boxes([], {})

    def _run_yolo(self):
        if not self._require_manager():
            return
        idx = self.player.current_frame_index
        ann = self.manager.auto_annotate_frame(idx)
        self.player.set_overlay_boxes(ann.boxes)
        self.ann_panel.update_boxes(ann.boxes, self.manager.yolo.class_names)
        self._set_status(f"YOLO found {len(ann.boxes)} object(s) in frame {idx}.")

    def _run_yolo_all(self):
        if not self._require_manager():
            return
        total = self.manager.total_count
        self._set_status("Running YOLO on all frames…")

        def progress(done, total_):
            self._set_status(f"YOLO annotating… {done}/{total_}")
            self.update_idletasks()

        self.manager.auto_annotate_all(progress_callback=progress)
        self._set_status(
            f"YOLO complete — {self.manager.annotated_count}/{total} frames annotated."
        )

    def _save(self):
        if not self._require_manager():
            return
        self.manager.save_annotations()
        self._set_status(
            f"Saved {self.manager.annotated_count} annotated frames to disk."
        )

    def _clear_frame(self):
        if not self._require_manager():
            return
        idx = self.player.current_frame_index
        self.manager.clear_frame(idx)
        self.player.set_overlay_boxes([])
        self.ann_panel.update_boxes([], {})

    # ── helpers ───────────────────────────────────────────────────────────────
    def _require_manager(self) -> bool:
        if self.manager is None:
            messagebox.showinfo("No video", "Please open a video first.")
            return False
        return True

    def _set_status(self, msg: str):
        self.status_var.set(msg)
        self.update_idletasks()

    def on_close(self):
        if self.manager:
            self.manager.loader.release()
        self.master.destroy()