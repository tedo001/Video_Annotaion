"""Canvas widget that displays video frames + bounding-box overlays."""
import tkinter as tk
from typing import List, Callable, Optional
from models.annotation_model import BoundingBox
from utils.image_utils import draw_boxes, bgr_to_photoimage
from utils.config import BG_DARK, BG_PANEL, ACCENT, TEXT_LIGHT


class VideoPlayer(tk.Frame):
    """
    Displays the current frame on a Canvas.
    Navigates frame-by-frame via slider and prev/next buttons.

    Parameters
    ----------
    on_frame_change : callable(frame_index, bgr_frame)
    """

    def __init__(self, master, on_frame_change: Callable = None):
        super().__init__(master, bg=BG_DARK)
        self._on_change  = on_frame_change
        self._loader     = None
        self._indices: List[int] = []
        self._pos        = 0           # index into self._indices
        self._boxes: List[BoundingBox] = []
        self._photo      = None        # keep reference to avoid GC
        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        self.canvas = tk.Canvas(self, bg="#0d0d1a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

        ctrl = tk.Frame(self, bg=BG_PANEL)
        ctrl.pack(fill=tk.X, pady=(4, 0))

        self.slider = tk.Scale(
            ctrl, from_=0, to=0, orient=tk.HORIZONTAL,
            command=self._on_slider, bg=BG_PANEL, fg=TEXT_LIGHT,
            troughcolor=BG_DARK, highlightthickness=0, sliderrelief=tk.FLAT,
        )
        self.slider.pack(fill=tk.X, padx=8, side=tk.TOP)

        btns = tk.Frame(ctrl, bg=BG_PANEL)
        btns.pack(pady=4)
        for text, cmd in [("⏮", self._go_first), ("◀", self._prev),
                          ("▶", self._next),      ("⏭", self._go_last)]:
            tk.Button(
                btns, text=text, command=cmd,
                bg=ACCENT, fg="white", relief=tk.FLAT,
                width=4, font=("Consolas", 11), cursor="hand2",
            ).pack(side=tk.LEFT, padx=3)

        self.idx_label = tk.Label(
            ctrl, text="Frame —", bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 9)
        )
        self.idx_label.pack(pady=(0, 4))

    # ── public API ────────────────────────────────────────────────────────────
    def load(self, loader, indices: List[int]):
        self._loader  = loader
        self._indices = indices
        self._pos     = 0
        if indices:
            self.slider.config(to=len(indices) - 1)
            self._show_current()

    def set_overlay_boxes(self, boxes: List[BoundingBox]):
        self._boxes = boxes
        self._redraw()

    @property
    def current_frame_index(self) -> int:
        if not self._indices:
            return 0
        return self._indices[self._pos]

    # ── navigation ────────────────────────────────────────────────────────────
    def _go_first(self): self._goto(0)
    def _go_last(self):  self._goto(len(self._indices) - 1)
    def _prev(self):     self._goto(self._pos - 1)
    def _next(self):     self._goto(self._pos + 1)

    def _on_slider(self, val):
        self._goto(int(val), update_slider=False)

    def _goto(self, pos: int, update_slider: bool = True):
        if not self._indices:
            return
        self._pos = max(0, min(pos, len(self._indices) - 1))
        if update_slider:
            self.slider.set(self._pos)
        self._show_current()

    def _show_current(self):
        if not self._loader or not self._indices:
            return
        idx   = self._indices[self._pos]
        frame = self._loader.read_frame(idx)
        if frame is None:
            return
        if self._on_change:
            self._on_change(idx, frame)
        self._current_frame = frame
        self.idx_label.config(
            text=f"Frame {idx}  ({self._pos + 1} / {len(self._indices)})"
        )
        self._redraw()

    def _redraw(self):
        if not hasattr(self, "_current_frame") or self._current_frame is None:
            return
        frame = self._current_frame
        if self._boxes:
            frame = draw_boxes(frame, self._boxes)
        w = self.canvas.winfo_width()  or 640
        h = self.canvas.winfo_height() or 480
        self._photo = bgr_to_photoimage(frame, w, h)
        self.canvas.delete("all")
        self.canvas.create_image(w // 2, h // 2, image=self._photo, anchor=tk.CENTER)