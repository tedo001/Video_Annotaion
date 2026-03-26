"""Right-hand side panel showing box list + action buttons."""
import tkinter as tk
from tkinter import ttk
from typing import List, Callable, Dict
from models.annotation_model import BoundingBox
from utils.config import BG_PANEL, BG_DARK, ACCENT, TEXT_LIGHT


class AnnotationPanel(tk.Frame):
    """
    Shows the list of BoundingBox objects for the current frame.
    Provides YOLO, Save, and Clear buttons.
    """

    def __init__(
        self,
        master,
        on_yolo_click:     Callable,
        on_yolo_all_click: Callable,
        on_save_click:     Callable,
        on_clear_click:    Callable,
    ):
        super().__init__(master, bg=BG_PANEL, width=260)
        self.pack_propagate(False)
        self._on_yolo     = on_yolo_click
        self._on_yolo_all = on_yolo_all_click
        self._on_save     = on_save_click
        self._on_clear    = on_clear_click
        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        tk.Label(
            self, text="ANNOTATIONS", bg=BG_PANEL, fg=ACCENT,
            font=("Consolas", 11, "bold"),
        ).pack(pady=(12, 4))

        # box list
        list_frame = tk.Frame(self, bg=BG_PANEL)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            bg=BG_DARK, fg=TEXT_LIGHT, selectbackground=ACCENT,
            font=("Consolas", 9), relief=tk.FLAT, bd=0,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # stats label
        self.stats_var = tk.StringVar(value="0 boxes")
        tk.Label(
            self, textvariable=self.stats_var,
            bg=BG_PANEL, fg=TEXT_LIGHT, font=("Consolas", 9),
        ).pack(pady=(4, 8))

        # action buttons
        for text, cmd in [
            ("⚡ YOLO This Frame", self._on_yolo),
            ("🔁 YOLO All Frames", self._on_yolo_all),
            ("💾 Save Annotations", self._on_save),
            ("🗑 Clear Frame",      self._on_clear),
        ]:
            tk.Button(
                self, text=text, command=cmd,
                bg=ACCENT, fg="white", relief=tk.FLAT,
                padx=8, pady=6, font=("Consolas", 9, "bold"),
                cursor="hand2", anchor=tk.W,
            ).pack(fill=tk.X, padx=8, pady=3)

    # ── public API ────────────────────────────────────────────────────────────
    def update_boxes(self, boxes: List[BoundingBox], class_names: Dict[int, str]):
        self.listbox.delete(0, tk.END)
        for i, box in enumerate(boxes):
            name = class_names.get(box.class_id, box.class_name)
            conf = f"{box.confidence:.2f}"
            self.listbox.insert(
                tk.END,
                f"  [{i:02d}] {name:<18} conf={conf}",
            )
        self.stats_var.set(f"{len(boxes)} box{'es' if len(boxes) != 1 else ''}")