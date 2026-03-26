"""
utils/
──────
Shared helpers and app-wide constants.
No layer-specific logic lives here — only pure utilities
that any other package may import safely.

Public API:
    from utils import config
    from utils import draw_boxes, resize_frame, bgr_to_photoimage, hex_to_bgr
"""

from utils.image_utils import (
    draw_boxes,
    resize_frame,
    bgr_to_photoimage,
    hex_to_bgr,
)
from utils import config

__all__ = [
    # image helpers
    "draw_boxes",
    "resize_frame",
    "bgr_to_photoimage",
    "hex_to_bgr",
    # config module (imported as a whole, not individual constants)
    "config",
]