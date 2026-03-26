"""Extracts frames from a video at a configurable step."""
import os
import cv2
from typing import Generator, Tuple
from core.video_loader import VideoLoader
from utils.config import FRAMES_DIR, DEFAULT_FPS_STEP
from utils.logger import get_logger

log = get_logger("core.FrameExtractor")


class FrameExtractor:
    def __init__(
        self,
        video_loader: VideoLoader,
        step: int        = DEFAULT_FPS_STEP,
        save_frames: bool= True,
    ):
        self.loader      = video_loader
        self.step        = max(1, step)
        self.save_frames = save_frames

        video_name       = os.path.splitext(
            os.path.basename(video_loader.video_path)
        )[0]
        self.output_dir  = os.path.join(FRAMES_DIR, video_name)
        os.makedirs(self.output_dir, exist_ok=True)

        log.info(
            f"FrameExtractor — step={self.step}, "
            f"save={self.save_frames}, dir={self.output_dir}"
        )

    def extract(self) -> Generator[Tuple[int, object, str], None, None]:
        total    = self.estimated_frame_count
        extracted = 0
        log.info(f"Starting extraction — ~{total} frames expected")

        self.loader.seek(0)
        for frame_idx in range(0, self.loader.total_frames, self.step):
            frame = self.loader.read_frame(frame_idx)
            if frame is None:
                log.warning(f"Skipped frame {frame_idx} — decode failed")
                continue
            saved_path = self._save(frame_idx, frame) if self.save_frames else ""
            extracted += 1
            if extracted % 100 == 0:
                log.debug(f"Extracted {extracted}/{total} frames…")
            yield frame_idx, frame, saved_path

        log.info(f"Extraction complete — {extracted} frames processed")

    def extract_single(self, frame_index: int) -> Tuple[object, str]:
        log.debug(f"Extracting single frame {frame_index}")
        frame = self.loader.read_frame(frame_index)
        if frame is None:
            log.warning(f"Frame {frame_index} could not be read")
            return None, ""
        saved_path = self._save(frame_index, frame) if self.save_frames else ""
        return frame, saved_path

    def _save(self, frame_idx: int, frame) -> str:
        filename = f"frame_{frame_idx:06d}.png"
        path     = os.path.join(self.output_dir, filename)
        cv2.imwrite(path, frame)
        log.debug(f"Saved frame {frame_idx} → {path}")
        return path

    def frame_path(self, frame_index: int) -> str:
        return os.path.join(self.output_dir, f"frame_{frame_index:06d}.png")

    @property
    def estimated_frame_count(self) -> int:
        return self.loader.total_frames // self.step