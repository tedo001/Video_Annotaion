"""
core/
────
Business-logic layer — video I/O, frame extraction,
YOLO inference, and annotation orchestration.

Public API (importable directly from `core`):
    from core import VideoLoader, FrameExtractor, YOLOAnnotator, AnnotationManager
"""

from core.video_loader       import VideoLoader
from core.frame_extractor    import FrameExtractor
from core.yolo_annotator     import YOLOAnnotator
from core.annotation_manager import AnnotationManager

__all__ = [
    "VideoLoader",
    "FrameExtractor",
    "YOLOAnnotator",
    "AnnotationManager",
]