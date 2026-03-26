"""
Canvas widget — displays frames + overlays.
Supports two modes:
  VIEW   : navigate frames only
  DRAW   : click-drag to draw a new bounding box
"""
import tkinter as tk
from typing import List, Callable, Optional

from models.annotation_model import BoundingBox
from utils.image_utils import draw_boxes, bgr_to_photoimage, resize_frame
from utils.config import BG_DARK, BG_PANEL, ACCENT, TEXT_LIGHT, BOX_COLOR


class VideoPlayer(tk.Frame):
    MODE_VIEW = "view"
    MODE_DRAW = "draw"

    def __init__(self, master, on_frame_change: Callable = None,
                 on_box_drawn: Callable = None):
        """
        Parameters
        ----------
        on_frame_change : callable(frame_index, bgr_frame)
        on_box_drawn    : callable(x1_norm, y1_norm, x2_norm, y2_norm)
                          called when user finishes drawing a box (normalised coords)
        """
        super().__init__(master, bg=BG_DARK)
        self._on_change   = on_frame_change
        self._on_box_drawn = on_box_drawn

        self._loader      = None
        self._indices: List[int] = []
        self._pos         = 0
        self._boxes: List[BoundingBox] = []
        self._photo       = None
        self._current_frame = None

        # ── draw-mode state ───────────────────────────────────────────────────
        self._mode        = self.MODE_VIEW
        self._draw_start: Optional[tuple] = None   # (canvas_x, canvas_y)
        self._draw_rect   = None                   # canvas rect id

        # frame→canvas offset (for aspect-ratio letterboxing)
        self._frame_offset_x = 0
        self._frame_offset_y = 0
        self._frame_scale    = 1.0
        self._frame_w        = 1
        self._frame_h        = 1

        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        # ── mode toggle bar ───────────────────────────────────────────────────
        mode_bar = tk.Frame(self, bg=BG_PANEL, height=32)
        mode_bar.pack(fill=tk.X)
        mode_bar.pack_propagate(False)

        tk.Label(
            mode_bar, text="  MODE:", bg=BG_PANEL, fg=TEXT_LIGHT,
            font=("Consolas", 9),
        ).pack(side=tk.LEFT, padx=(8, 4), pady=6)

        self._view_btn = tk.Button(
            mode_bar, text="👁 View", command=self.set_view_mode,
            bg=ACCENT, fg="white", relief=tk.FLAT,
            padx=10, font=("Consolas", 9, "bold"), cursor="hand2",
        )
        self._view_btn.pack(side=tk.LEFT, padx=2, pady=4)

        self._draw_btn = tk.Button(
            mode_bar, text="✏ Draw Box", command=self.set_draw_mode,
            bg=BG_DARK, fg=TEXT_LIGHT, relief=tk.FLAT,
            padx=10, font=("Consolas", 9, "bold"), cursor="hand2",
        )
        self._draw_btn.pack(side=tk.LEFT, padx=2, pady=4)

        self._mode_label = tk.Label(
            mode_bar, text="  VIEW MODE — navigate freely",
            bg=BG_PANEL, fg="#aaaacc", font=("Consolas", 8, "italic"),
        )
        self._mode_label.pack(side=tk.LEFT, padx=12)

        # ── canvas ────────────────────────────────────────────────────────────
        self.canvas = tk.Canvas(self, bg="#0d0d1a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

        # mouse events (always bound — gated by mode inside handlers)
        self.canvas.bind("<ButtonPress-1>",   self._on_mouse_press)
        self.canvas.bind("<B1-Motion>",       self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)

        # ── controls ──────────────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG_PANEL)
        ctrl.pack(fill=tk.X, pady=(2, 0))

        self.slider = tk.Scale(
            ctrl, from_=0, to=0, orient=tk.HORIZONTAL,
            command=self._on_slider,
            bg=BG_PANEL, fg=TEXT_LIGHT, troughcolor=BG_DARK,
            highlightthickness=0, sliderrelief=tk.FLAT,
        )
        self.slider.pack(fill=tk.X, padx=8)

        btns = tk.Frame(ctrl, bg=BG_PANEL)
        btns.pack(pady=4)

        for text, cmd in [
            ("⏮", self._go_first), ("◀", self._prev),
            ("▶", self._next),     ("⏭", self._go_last),
        ]:
            tk.Button(
                btns, text=text, command=cmd,
                bg=ACCENT, fg="white", relief=tk.FLAT,
                width=4, font=("Consolas", 11), cursor="hand2",
            ).pack(side=tk.LEFT, padx=3)

        self.idx_label = tk.Label(
            ctrl, text="Frame —",
            bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 9),
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
        self._boxes = list(boxes)
        self._redraw()

    @property
    def current_frame_index(self) -> int:
        if not self._indices:
            return 0
        return self._indices[self._pos]

    # ── mode switching ────────────────────────────────────────────────────────
    def set_view_mode(self):
        self._mode = self.MODE_VIEW
        self.canvas.config(cursor="arrow")
        self._view_btn.config(bg=ACCENT,   fg="white")
        self._draw_btn.config(bg=BG_DARK,  fg=TEXT_LIGHT)
        self._mode_label.config(text="  VIEW MODE — navigate freely")
        self._cancel_draw()

    def set_draw_mode(self):
        self._mode = self.MODE_DRAW
        self.canvas.config(cursor="crosshair")
        self._draw_btn.config(bg="#e05c5c", fg="white")
        self._view_btn.config(bg=BG_DARK,  fg=TEXT_LIGHT)
        self._mode_label.config(
            text="  DRAW MODE — click & drag to annotate"
        )

    def is_draw_mode(self) -> bool:
        return self._mode == self.MODE_DRAW

    # ── mouse handlers ────────────────────────────────────────────────────────
    def _on_mouse_press(self, event):
        if self._mode != self.MODE_DRAW:
            return
        self._draw_start = (event.x, event.y)
        if self._draw_rect:
            self.canvas.delete(self._draw_rect)
        self._draw_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#ff4444", width=2, dash=(4, 4),
        )

    def _on_mouse_drag(self, event):
        if self._mode != self.MODE_DRAW or self._draw_start is None:
            return
        x0, y0 = self._draw_start
        self.canvas.coords(self._draw_rect, x0, y0, event.x, event.y)

    def _on_mouse_release(self, event):
        if self._mode != self.MODE_DRAW or self._draw_start is None:
            return
        x0, y0 = self._draw_start
        x1, y1 = event.x, event.y

        # Clean up ghost rectangle
        if self._draw_rect:
            self.canvas.delete(self._draw_rect)
            self._draw_rect = None
        self._draw_start = None

        # Ignore tiny accidental clicks
        if abs(x1 - x0) < 8 or abs(y1 - y0) < 8:
            return

        # Convert canvas coords → normalised image coords
        norm = self._canvas_to_norm(x0, y0, x1, y1)
        if norm and self._on_box_drawn:
            self._on_box_drawn(*norm)

    def _cancel_draw(self):
        if self._draw_rect:
            self.canvas.delete(self._draw_rect)
            self._draw_rect = None
        self._draw_start = None

    # ── coord conversion ──────────────────────────────────────────────────────
    def _canvas_to_norm(self, cx0, cy0, cx1, cy1):
        """
        Convert canvas pixel rect → (x1_n, y1_n, x2_n, y2_n) normalised to
        the *original frame* dimensions. Returns None if frame not loaded.
        """
        if self._frame_scale == 0:
            return None

        ox, oy = self._frame_offset_x, self._frame_offset_y
        sc     = self._frame_scale

        # Clamp to frame area
        fw = self._frame_w * sc
        fh = self._frame_h * sc

        ix0 = max(0.0, min((cx0 - ox) / sc, self._frame_w))
        iy0 = max(0.0, min((cy0 - oy) / sc, self._frame_h))
        ix1 = max(0.0, min((cx1 - ox) / sc, self._frame_w))
        iy1 = max(0.0, min((cy1 - oy) / sc, self._frame_h))

        # Normalise to [0, 1]
        nx0 = ix0 / self._frame_w
        ny0 = iy0 / self._frame_h
        nx1 = ix1 / self._frame_w
        ny1 = iy1 / self._frame_h

        # Ensure top-left < bottom-right
        return (min(nx0, nx1), min(ny0, ny1),
                max(nx0, nx1), max(ny0, ny1))

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
        self._current_frame = frame
        self._frame_h, self._frame_w = frame.shape[:2]
        self.idx_label.config(
            text=f"Frame {idx}  ({self._pos + 1} / {len(self._indices)})"
        )
        if self._on_change:
            self._on_change(idx, frame)
        self._redraw()

    # ── rendering ─────────────────────────────────────────────────────────────
    def _redraw(self):
        if self._current_frame is None:
            return

        cw = self.canvas.winfo_width()  or 640
        ch = self.canvas.winfo_height() or 480
        fh, fw = self._current_frame.shape[:2]

        # Compute letterbox scale + offsets
        scale  = min(cw / fw, ch / fh)
        nw, nh = int(fw * scale), int(fh * scale)
        ox     = (cw - nw) // 2
        oy     = (ch - nh) // 2

        self._frame_scale    = scale
        self._frame_offset_x = ox
        self._frame_offset_y = oy
        self._frame_w        = fw
        self._frame_h        = fh

        frame = self._current_frame
        if self._boxes:
            from utils.image_utils import draw_boxes
            frame = draw_boxes(frame, self._boxes)

        from utils.image_utils import bgr_to_photoimage
        self._photo = bgr_to_photoimage(frame, cw, ch)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2,
                                 image=self._photo, anchor=tk.CENTER)