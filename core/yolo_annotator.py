"""YOLOv8 inference wrapper — thread-safe, with logging."""
import os
import threading
from typing import List
from ultralytics import YOLO
from models.annotation_model import BoundingBox
from utils.config import YOLO_MODEL_PATH, YOLO_CONFIDENCE, YOLO_IOU_THRESHOLD
from utils.logger import get_logger

log = get_logger("core.YOLOAnnotator")


class YOLOAnnotator:
    def __init__(
        self,
        model_path: str   = YOLO_MODEL_PATH,
        confidence: float = YOLO_CONFIDENCE,
        iou:        float = YOLO_IOU_THRESHOLD,
    ):
        self.confidence = confidence
        self.iou        = iou
        self.model_path = model_path
        self._model     = None
        self._lock      = threading.Lock()
        log.debug(
            f"YOLOAnnotator created — conf={confidence}, iou={iou}, "
            f"model_path={model_path}"
        )

    def load(self):
        with self._lock:
            if self._model is not None:
                return
            weights = (
                self.model_path
                if os.path.exists(self.model_path)
                else "yolov8n.pt"
            )
            log.info(f"Loading YOLO weights: {weights}")
            try:
                self._model = YOLO(weights)
                log.info(
                    f"YOLO model loaded — "
                    f"{len(self._model.names)} classes available"
                )
                log.debug(f"Classes: {self._model.names}")
            except Exception as exc:
                log.error(f"Failed to load YOLO model: {exc}", exc_info=True)
                raise

    def is_loaded(self) -> bool:
        return self._model is not None

    def annotate_frame(self, bgr_frame) -> List[BoundingBox]:
        self.load()
        log.debug(
            f"Running inference — conf={self.confidence}, iou={self.iou}"
        )
        try:
            results = self._model.predict(
                source  = bgr_frame,
                conf    = self.confidence,
                iou     = self.iou,
                verbose = False,
            )
        except Exception as exc:
            log.error(f"YOLO inference error: {exc}", exc_info=True)
            return []

        boxes: List[BoundingBox] = []
        for result in results:
            img_h, img_w = bgr_frame.shape[:2]
            for box in result.boxes:
                cls_id   = int(box.cls[0])
                cls_name = result.names[cls_id]
                conf     = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = ((x1 + x2) / 2) / img_w
                cy = ((y1 + y2) / 2) / img_h
                bw = (x2 - x1) / img_w
                bh = (y2 - y1) / img_h
                boxes.append(BoundingBox(
                    class_id=cls_id, class_name=cls_name,
                    x_center=cx, y_center=cy,
                    width=bw, height=bh, confidence=conf,
                ))
                log.debug(
                    f"  Detected: {cls_name} conf={conf:.2f} "
                    f"bbox=({cx:.3f},{cy:.3f},{bw:.3f},{bh:.3f})"
                )

        log.info(f"Inference complete — {len(boxes)} object(s) detected")
        return boxes

    @property
    def class_names(self) -> dict:
        return self._model.names if self._model else {}