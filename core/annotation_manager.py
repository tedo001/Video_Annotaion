"""Orchestrates the annotation lifecycle for an entire video."""
from typing import Dict, Optional, List
from models.annotation_model import FrameAnnotation, BoundingBox
from core.video_loader    import VideoLoader
from core.frame_extractor import FrameExtractor
from core.yolo_annotator  import YOLOAnnotator
from storage.frame_storage import FrameStorage
from storage.label_storage import LabelStorage


class AnnotationManager:
    """
    Central controller — connects VideoLoader, FrameExtractor,
    YOLOAnnotator, FrameStorage, and LabelStorage.

    Workflow
    --------
    mgr = AnnotationManager(loader, extractor, yolo, frame_store, label_store)
    mgr.load_video()
    mgr.auto_annotate_frame(42)
    mgr.save_annotations()
    """

    def __init__(
        self,
        video_loader:   VideoLoader,
        frame_extractor: FrameExtractor,
        yolo_annotator:  YOLOAnnotator,
        frame_storage:   "FrameStorage",
        label_storage:   "LabelStorage",
    ):
        self.loader    = video_loader
        self.extractor = frame_extractor
        self.yolo      = yolo_annotator
        self.f_store   = frame_storage
        self.l_store   = label_storage

        # frame_index → FrameAnnotation
        self._annotations: Dict[int, FrameAnnotation] = {}

    # ── video load ────────────────────────────────────────────────────────────
    def load_video(self):
        """Extract all frames (respecting step) and register them."""
        self._annotations.clear()
        for idx, frame, saved_path in self.extractor.extract():
            ann = FrameAnnotation(frame_index=idx, frame_path=saved_path)
            self._annotations[idx] = ann

    # ── annotation helpers ────────────────────────────────────────────────────
    def get_annotation(self, frame_index: int) -> Optional[FrameAnnotation]:
        return self._annotations.get(frame_index)

    def all_frame_indices(self) -> List[int]:
        return sorted(self._annotations.keys())

    # ── YOLO auto-annotation ──────────────────────────────────────────────────
    def auto_annotate_frame(self, frame_index: int) -> FrameAnnotation:
        """Run YOLO on one frame and store results."""
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
        return ann

    def auto_annotate_all(self, progress_callback=None):
        """Auto-annotate every extracted frame. progress_callback(done, total)."""
        indices = self.all_frame_indices()
        for i, idx in enumerate(indices):
            self.auto_annotate_frame(idx)
            if progress_callback:
                progress_callback(i + 1, len(indices))

    # ── manual box editing ────────────────────────────────────────────────────
    def add_box(self, frame_index: int, box: BoundingBox):
        ann = self._annotations.get(frame_index)
        if ann:
            ann.add_box(box)

    def remove_box(self, frame_index: int, box_index: int):
        ann = self._annotations.get(frame_index)
        if ann:
            ann.remove_box(box_index)

    def clear_frame(self, frame_index: int):
        ann = self._annotations.get(frame_index)
        if ann:
            ann.clear_boxes()

    # ── persistence ───────────────────────────────────────────────────────────
    def save_annotations(self):
        """Persist all labels to disk."""
        for ann in self._annotations.values():
            if ann.is_annotated:
                label_path = self.l_store.save(ann)
                ann.label_path = label_path

    def load_existing_labels(self):
        """Re-load labels from disk into annotation objects."""
        for ann in self._annotations.values():
            loaded = self.l_store.load(ann.frame_path)
            if loaded:
                ann.boxes = loaded
                ann.is_annotated = True

    # ── stats ─────────────────────────────────────────────────────────────────
    @property
    def annotated_count(self) -> int:
        return sum(1 for a in self._annotations.values() if a.is_annotated)

    @property
    def total_count(self) -> int:
        return len(self._annotations)