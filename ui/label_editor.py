"""Simple dialog for manually editing or adding a bounding box label."""
import tkinter as tk
from tkinter import ttk, simpledialog
from typing import Optional
from models.annotation_model import BoundingBox
from utils.config import BG_PANEL, BG_DARK, ACCENT, TEXT_LIGHT


class LabelEditorDialog(tk.Toplevel):
    """
    Modal dialog to create or edit one BoundingBox.

    Opens with LabelEditorDialog.ask(...) which returns a BoundingBox or None.
    """

    def __init__(self, master, class_names: dict, existing: Optional[BoundingBox] = None):
        super().__init__(master)
        self.title("Edit Label")
        self.resizable(False, False)
        self.configure(bg=BG_PANEL)
        self.grab_set()

        self._class_names = class_names
        self._existing    = existing
        self._result: Optional[BoundingBox] = None
        self._build()
        self.wait_window()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        pad = {"padx": 10, "pady": 5}

        tk.Label(self, text="Class Name", bg=BG_PANEL, fg=TEXT_LIGHT,
                 font=("Consolas", 10)).grid(row=0, column=0, sticky=tk.W, **pad)

        names = list(self._class_names.values()) if self._class_names else ["object"]
        self._cls_var = tk.StringVar(value=self._existing.class_name if self._existing else names[0])
        ttk.Combobox(self, textvariable=self._cls_var, values=names, width=22).grid(
            row=0, column=1, **pad
        )

        fields = [
            ("X Center (0-1)", "x_center"),
            ("Y Center (0-1)", "y_center"),
            ("Width   (0-1)",  "width"),
            ("Height  (0-1)",  "height"),
        ]
        self._vars = {}
        for r, (label, attr) in enumerate(fields, start=1):
            tk.Label(self, text=label, bg=BG_PANEL, fg=TEXT_LIGHT,
                     font=("Consolas", 10)).grid(row=r, column=0, sticky=tk.W, **pad)
            v = tk.StringVar(value=str(getattr(self._existing, attr, 0.5)) if self._existing else "0.5")
            tk.Entry(self, textvariable=v, width=12, bg=BG_DARK, fg=TEXT_LIGHT,
                     insertbackground=TEXT_LIGHT, relief=tk.FLAT).grid(row=r, column=1, **pad)
            self._vars[attr] = v

        tk.Button(self, text="OK", command=self._confirm,
                  bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=12, font=("Consolas", 10, "bold")).grid(
            row=6, column=0, columnspan=2, pady=10
        )

    def _confirm(self):
        try:
            cls_name = self._cls_var.get()
            cls_id   = next(
                (k for k, v in self._class_names.items() if v == cls_name), 0
            )
            self._result = BoundingBox(
                class_id   = cls_id,
                class_name = cls_name,
                x_center   = float(self._vars["x_center"].get()),
                y_center   = float(self._vars["y_center"].get()),
                width      = float(self._vars["width"].get()),
                height     = float(self._vars["height"].get()),
            )
            self.destroy()
        except ValueError as e:
            tk.messagebox.showerror("Invalid input", str(e), parent=self)

    # ── factory ───────────────────────────────────────────────────────────────
    @classmethod
    def ask(cls, master, class_names: dict,
            existing: Optional[BoundingBox] = None) -> Optional[BoundingBox]:
        dialog = cls(master, class_names, existing)
        return dialog._result