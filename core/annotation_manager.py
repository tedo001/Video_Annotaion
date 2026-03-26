"""Orchestrates annotation lifecycle — with logging."""
from typing import Dict, Optional, List
from models.annotation_model import FrameAnnotation, BoundingBox
from core.video_loader       import VideoLoader
from core.frame_extractor    import FrameExtractor
from core.yolo_annotator     import YOLOAnnotator
from storage.frame_storage   import FrameStorage
from storage.label_storage   import LabelStorage
from utils.logger            import get_logger

log = get_logger("core.AnnotationManager")


class AnnotationManager:
    def __init__(
        self,
        video_loader:    VideoLoader,
        frame_extractor: FrameExtractor,
        yolo_annotator:  YOLOAnnotator,
        frame_storage:   FrameStorage,
        label_storage:   LabelStorage,
    ):
        self.loader    = video_loader
        self.extractor = frame_extractor
        self.yolo      = yolo_annotator
        self.f_store   = frame_storage
        self.l_store   = label_storage
        self._annotations: Dict[int, FrameAnnotation] = {}
        log.info("AnnotationManager initialised")

    def load_video(self):
        log.info("Loading video frames into manager…")
        self._annotations.clear()
        for idx, frame, saved_path in self.extractor.extract():
            self._annotations[idx] = FrameAnnotation(
                frame_index=idx, frame_path=saved_path
            )
        log.info(f"Loaded {len(self._annotations)} frames")

    def get_annotation(self, frame_index: int) -> Optional[FrameAnnotation]:
        return self._annotations.get(frame_index)

    def all_frame_indices(self) -> List[int]:
        return sorted(self._annotations.keys())

    def auto_annotate_frame(self, frame_index: int) -> FrameAnnotation:
        log.debug(f"Auto-annotating frame {frame_index}")
        ann = self._annotations.get(frame_index)
        if ann is None:
            frame, saved_path = self.extractor.extract_single(frame_index)
            ann = FrameAnnotation(frame_index=frame_index, frame_path=saved_path)
            self._annotations[frame_index] = ann
        else:
            frame = self.loader.read_frame(frame_index)

        ann.clear_boxes()
        if frame is not None:
            boxes = self.yolo.annotate_frame(frame)
            for box in boxes:
                ann.add_box(box)
        log.info(
            f"Frame {frame_index} auto-annotated — "
            f"{len(ann.boxes)} box(es)"
        )
        return ann

    def auto_annotate_all(self, progress_callback=None):
        indices = self.all_frame_indices()
        log.info(f"Auto-annotating all {len(indices)} frames…")
        for i, idx in enumerate(indices):
            self.auto_annotate_frame(idx)
            if progress_callback:
                progress_callback(i + 1, len(indices))
        log.info(
            f"Bulk annotation complete — "
            f"{self.annotated_count}/{self.total_count} annotated"
        )

    def add_box(self, frame_index: int, box: BoundingBox):
        ann = self._annotations.get(frame_index)
        if ann:
            ann.add_box(box)
            log.info(
                f"Manual box added to frame {frame_index} — "
                f"class='{box.class_name}' "
                f"cx={box.x_center:.3f} cy={box.y_center:.3f}"
            )

    def remove_box(self, frame_index: int, box_index: int):
        ann = self._annotations.get(frame_index)
        if ann:
            removed = ann.boxes[box_index] if 0 <= box_index < len(ann.boxes) else None
            ann.remove_box(box_index)
            if removed:
                log.info(
                    f"Box [{box_index}] removed from frame {frame_index} "
                    f"— was '{removed.class_name}'"
                )

    def clear_frame(self, frame_index: int):
        ann = self._annotations.get(frame_index)
        if ann:
            n = len(ann.boxes)
            ann.clear_boxes()
            log.info(f"Cleared {n} box(es) from frame {frame_index}")

    def save_annotations(self):
        saved = 0
        for ann in self._annotations.values():
            if ann.is_annotated:
                label_path     = self.l_store.save(ann)
                ann.label_path = label_path
                saved         += 1
                log.debug(f"Saved frame {ann.frame_index} → {label_path}")
        log.info(f"Save complete — {saved} label file(s) written")

    def load_existing_labels(self):
        loaded = 0
        for ann in self._annotations.values():
            boxes = self.l_store.load(ann.frame_path)
            if boxes:
                ann.boxes        = boxes
                ann.is_annotated = True
                loaded          += 1
        log.info(f"Loaded existing labels for {loaded} frame(s)")

    @property
    def annotated_count(self) -> int:
        return sum(1 for a in self._annotations.values() if a.is_annotated)

    @property
    def total_count(self) -> int:
        return len(self._annotations)