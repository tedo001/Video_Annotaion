"""Extracts frames from a video at a configurable step."""
import os
import cv2
from typing import Generator, Tuple
from core.video_loader import VideoLoader
from utils.config import FRAMES_DIR, DEFAULT_FPS_STEP


class FrameExtractor:
    """
    Walks through a VideoLoader and yields (index, BGR-array) pairs.
    Optionally saves frames to disk.

    Parameters
    ----------
    video_loader : VideoLoader   already-open loader
    step         : int           extract every `step`-th frame (default 1)
    save_frames  : bool          write PNG files to FRAMES_DIR
    """

    def __init__(
        self,
        video_loader: VideoLoader,
        step: int = DEFAULT_FPS_STEP,
        save_frames: bool = True,
    ):
        self.loader      = video_loader
        self.step        = max(1, step)
        self.save_frames = save_frames

        # output subfolder per video
        video_name = os.path.splitext(os.path.basename(video_loader.video_path))[0]
        self.output_dir = os.path.join(FRAMES_DIR, video_name)
        os.makedirs(self.output_dir, exist_ok=True)

    # ── main iterator ─────────────────────────────────────────────────────────
    def extract(self) -> Generator[Tuple[int, object, str], None, None]:
        """
        Yields
        ------
        (frame_index, bgr_frame, saved_path)
        saved_path is "" when save_frames=False.
        """
        self.loader.seek(0)
        for frame_idx in range(0, self.loader.total_frames, self.step):
            frame = self.loader.read_frame(frame_idx)
            if frame is None:
                continue
            saved_path = ""
            if self.save_frames:
                saved_path = self._save(frame_idx, frame)
            yield frame_idx, frame, saved_path

    def extract_single(self, frame_index: int) -> Tuple[object, str]:
        """Extract and optionally save one specific frame."""
        frame = self.loader.read_frame(frame_index)
        if frame is None:
            return None, ""
        saved_path = self._save(frame_index, frame) if self.save_frames else ""
        return frame, saved_path

    # ── helpers ───────────────────────────────────────────────────────────────
    def _save(self, frame_idx: int, frame) -> str:
        filename = f"frame_{frame_idx:06d}.png"
        path     = os.path.join(self.output_dir, filename)
        cv2.imwrite(path, frame)
        return path

    def frame_path(self, frame_index: int) -> str:
        return os.path.join(self.output_dir, f"frame_{frame_index:06d}.png")

    @property
    def estimated_frame_count(self) -> int:
        return self.loader.total_frames // self.step