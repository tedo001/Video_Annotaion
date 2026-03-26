"""Utility functions for drawing and resizing."""
import cv2
import numpy as np
from typing import List, Tuple
from models.annotation_model import BoundingBox
from utils.config import BOX_COLOR


def draw_boxes(bgr_frame, boxes: List[BoundingBox], color=BOX_COLOR) -> np.ndarray:
    """Return a copy of bgr_frame with all bounding boxes drawn."""
    frame = bgr_frame.copy()
    h, w  = frame.shape[:2]
    bgr   = hex_to_bgr(color)
    for box in boxes:
        x1, y1, x2, y2 = box.to_pixel_coords(w, h)
        cv2.rectangle(frame, (x1, y1), (x2, y2), bgr, 2)
        label = f"{box.class_name} {box.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), bgr, -1)
        cv2.putText(
            frame, label, (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA,
        )
    return frame


def resize_frame(frame, width: int, height: int) -> np.ndarray:
    """Resize keeping aspect ratio, padding with black bars."""
    h, w = frame.shape[:2]
    scale = min(width / w, height / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas  = np.zeros((height, width, 3), dtype=np.uint8)
    y_off   = (height - nh) // 2
    x_off   = (width  - nw) // 2
    canvas[y_off:y_off+nh, x_off:x_off+nw] = resized
    return canvas


def bgr_to_photoimage(bgr_frame, width: int, height: int):
    """Convert BGR frame → Tkinter PhotoImage."""
    from PIL import Image, ImageTk
    resized = resize_frame(bgr_frame, width, height)
    rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return ImageTk.PhotoImage(Image.fromarray(rgb))


def hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return b, g, r