"""
core/image_loader.py
─────────────────────
Loads a single image OR a folder of images.
Presents a unified interface matching VideoLoader so
AnnotationManager can work with both without changes.
"""
import os
import cv2
import numpy as np
from typing import List, Optional
from utils.logger import get_logger


def _safe_imread(path: str):
    """
    cv2.imread() silently returns None on Windows when the path contains
    dots, spaces, or non-ASCII characters.
    np.fromfile + imdecode works correctly on ALL Windows paths.
    """
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None

log = get_logger("core.ImageLoader")

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


class ImageLoader:
    """
    Mimics the VideoLoader API so the rest of the pipeline is reusable.

    Attributes
    ----------
    source_path   : str   — original file or folder path
    image_paths   : list  — sorted list of absolute image paths
    total_frames  : int   — alias for len(image_paths)
    fps           : float — always 1.0 (one frame per image)
    width / height: int   — dimensions of the FIRST image (reference)
    """

    def __init__(self, source_path: str):
        self.source_path  = source_path
        self.image_paths: List[str] = []
        self.total_frames = 0
        self.fps          = 1.0
        self.width        = 0
        self.height       = 0
        self.duration_sec = 0.0
        self._current_pos = 0
        log.debug(f"ImageLoader created — source: {source_path}")

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def open(self) -> bool:
        if os.path.isfile(self.source_path):
            ext = os.path.splitext(self.source_path)[1].lower()
            if ext not in SUPPORTED_EXTS:
                raise ValueError(f"Unsupported image format: {ext}")
            self.image_paths = [self.source_path]
            log.info(f"Single image loaded: {self.source_path}")

        elif os.path.isdir(self.source_path):
            all_files = sorted(os.listdir(self.source_path))
            self.image_paths = [
                os.path.join(self.source_path, f)
                for f in all_files
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
            ]
            if not self.image_paths:
                raise FileNotFoundError(
                    f"No supported images found in: {self.source_path}"
                )
            log.info(
                f"Image folder loaded — {len(self.image_paths)} images "
                f"from: {self.source_path}"
            )
        else:
            raise FileNotFoundError(f"Path not found: {self.source_path}")

        self.total_frames = len(self.image_paths)
        self.duration_sec = float(self.total_frames)

        # Read first image for dimensions
        sample = _safe_imread(self.image_paths[0])
        if sample is not None:
            self.height, self.width = sample.shape[:2]
            log.info(f"Reference dimensions: {self.width}x{self.height}")
        return True

    def release(self):
        log.info("ImageLoader released")
        self.image_paths  = []
        self.total_frames = 0
        self._current_pos = 0

    def is_open(self) -> bool:
        return bool(self.image_paths)

    # ── frame access ──────────────────────────────────────────────────────────
    def read_frame(self, frame_index: int) -> Optional[np.ndarray]:
        if not self.is_open():
            raise RuntimeError("ImageLoader is not open.")
        if not (0 <= frame_index < self.total_frames):
            log.warning(f"Frame index {frame_index} out of range")
            return None
        path  = self.image_paths[frame_index]
        frame = _safe_imread(path)
        if frame is None:
            log.warning(f"Could not read image: {path}")
        return frame

    def read_next_frame(self):
        if self._current_pos >= self.total_frames:
            return None, None
        idx   = self._current_pos
        frame = self.read_frame(idx)
        self._current_pos += 1
        return (idx, frame) if frame is not None else (None, None)

    def seek(self, frame_index: int):
        self._current_pos = max(0, min(frame_index, self.total_frames - 1))

    @property
    def current_position(self) -> int:
        return self._current_pos

    # ── helpers ───────────────────────────────────────────────────────────────
    def get_image_path(self, frame_index: int) -> str:
        if 0 <= frame_index < len(self.image_paths):
            return self.image_paths[frame_index]
        return ""

    @property
    def is_folder(self) -> bool:
        return os.path.isdir(self.source_path)

    def __repr__(self):
        return (
            f"ImageLoader(source={self.source_path!r}, "
            f"count={self.total_frames})"
        )