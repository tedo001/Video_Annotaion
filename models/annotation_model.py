"""Pure-data model classes (no I/O)."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BoundingBox:
    """
    Stores one bounding box in YOLO normalised format.
    x_center, y_center, width, height — all in [0, 1].
    """
    class_id:   int
    class_name: str
    x_center:   float
    y_center:   float
    width:      float
    height:     float
    confidence: float = 1.0          # 1.0 for manual, model score for YOLO

    # ── pixel helpers ─────────────────────────────────────────────────────────
    def to_pixel_coords(self, img_w: int, img_h: int):
        """Return (x1, y1, x2, y2) in pixel coordinates."""
        cx = self.x_center * img_w
        cy = self.y_center * img_h
        w  = self.width    * img_w
        h  = self.height   * img_h
        return int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)

    def to_yolo_line(self) -> str:
        return (
            f"{self.class_id} {self.x_center:.6f} {self.y_center:.6f} "
            f"{self.width:.6f} {self.height:.6f}"
        )


@dataclass
class FrameAnnotation:
    """All annotations belonging to one video frame."""
    frame_index:  int
    frame_path:   str                         # absolute path to saved image
    label_path:   Optional[str] = None        # absolute path to saved label file
    boxes:        List[BoundingBox] = field(default_factory=list)
    is_annotated: bool = False

    def add_box(self, box: BoundingBox):
        self.boxes.append(box)
        self.is_annotated = bool(self.boxes)

    def remove_box(self, index: int):
        if 0 <= index < len(self.boxes):
            self.boxes.pop(index)
        self.is_annotated = bool(self.boxes)

    def clear_boxes(self):
        self.boxes.clear()
        self.is_annotated = False