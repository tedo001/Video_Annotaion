"""Responsible for opening a video file and exposing its metadata."""
import cv2
from typing import Optional


class VideoLoader:
    """
    Opens a video file with OpenCV and exposes metadata.

    Usage
    -----
    loader = VideoLoader("clip.mp4")
    loader.open()
    frame = loader.read_frame(42)
    loader.release()
    """

    def __init__(self, video_path: str):
        self.video_path = video_path
        self._cap: Optional[cv2.VideoCapture] = None

        # populated after open()
        self.total_frames: int  = 0
        self.fps:          float = 0.0
        self.width:        int  = 0
        self.height:       int  = 0
        self.duration_sec: float = 0.0

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self.video_path)
        if not self._cap.isOpened():
            raise IOError(f"Cannot open video: {self.video_path}")
        self.total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps          = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.width        = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height       = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration_sec = self.total_frames / self.fps
        return True

    def release(self):
        if self._cap:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ── frame access ──────────────────────────────────────────────────────────
    def read_frame(self, frame_index: int):
        """Return a BGR numpy array for the requested frame index, or None."""
        if not self.is_open():
            raise RuntimeError("VideoLoader is not open. Call open() first.")
        if not (0 <= frame_index < self.total_frames):
            return None
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self._cap.read()
        return frame if ret else None

    def read_next_frame(self):
        """Read the next frame sequentially. Returns (index, frame) or (None, None)."""
        if not self.is_open():
            return None, None
        idx = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        ret, frame = self._cap.read()
        return (idx, frame) if ret else (None, None)

    def seek(self, frame_index: int):
        if self.is_open():
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

    # ── properties ────────────────────────────────────────────────────────────
    @property
    def current_position(self) -> int:
        if self._cap:
            return int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        return 0

    def __repr__(self):
        return (
            f"VideoLoader(path={self.video_path!r}, "
            f"frames={self.total_frames}, fps={self.fps:.1f})"
        )