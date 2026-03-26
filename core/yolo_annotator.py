"""YOLOv8 inference wrapper — auto-downloads weights on first run."""
import os
from typing import List
from ultralytics import YOLO
from models.annotation_model import BoundingBox
from utils.config import YOLO_MODEL_PATH, YOLO_CONFIDENCE, YOLO_IOU_THRESHOLD


class YOLOAnnotator:
    """
    Wraps a YOLOv8 model and converts predictions to BoundingBox objects.

    Parameters
    ----------
    model_path  : str    path to .pt weights (downloads yolov8n.pt if missing)
    confidence  : float  minimum score threshold
    iou         : float  NMS IoU threshold
    """

    def __init__(
        self,
        model_path: str   = YOLO_MODEL_PATH,
        confidence: float = YOLO_CONFIDENCE,
        iou:        float = YOLO_IOU_THRESHOLD,
    ):
        self.confidence = confidence
        self.iou        = iou
        self._model     = None
        self.model_path = model_path

    # ── lazy load ─────────────────────────────────────────────────────────────
    def load(self):
        """Load (or download) the YOLO model. Safe to call multiple times."""
        if self._model is None:
            # If custom path doesn't exist, fall back to ultralytics auto-download
            weights = self.model_path if os.path.exists(self.model_path) else "yolov8n.pt"
            self._model = YOLO(weights)
            print(f"[YOLOAnnotator] Loaded model: {weights}")

    def is_loaded(self) -> bool:
        return self._model is not None

    # ── inference ─────────────────────────────────────────────────────────────
    def annotate_frame(self, bgr_frame) -> List[BoundingBox]:
        """
        Run inference on a single BGR numpy frame.

        Returns
        -------
        List[BoundingBox]  in YOLO normalised format.
        """
        self.load()
        results = self._model.predict(
            source    = bgr_frame,
            conf      = self.confidence,
            iou       = self.iou,
            verbose   = False,
        )
        boxes: List[BoundingBox] = []
        for result in results:
            img_h, img_w = bgr_frame.shape[:2]
            for box in result.boxes:
                cls_id   = int(box.cls[0])
                cls_name = result.names[cls_id]
                conf     = float(box.conf[0])
                # xyxy → normalised xywh
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = ((x1 + x2) / 2) / img_w
                cy = ((y1 + y2) / 2) / img_h
                bw = (x2 - x1)       / img_w
                bh = (y2 - y1)       / img_h
                boxes.append(
                    BoundingBox(
                        class_id   = cls_id,
                        class_name = cls_name,
                        x_center   = cx,
                        y_center   = cy,
                        width      = bw,
                        height     = bh,
                        confidence = conf,
                    )
                )
        return boxes

    # ── class names ───────────────────────────────────────────────────────────
    @property
    def class_names(self) -> dict:
        if self._model:
            return self._model.names
        return {}