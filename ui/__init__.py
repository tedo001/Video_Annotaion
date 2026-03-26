"""
ui/
───
Tkinter presentation layer.
All widgets are self-contained and communicate upward
via callbacks — they never import from each other directly.

Public API:
    from ui import MainWindow, VideoPlayer, AnnotationPanel, LabelEditorDialog
"""

from ui.main_window      import MainWindow
from ui.video_player     import VideoPlayer
from ui.annotation_panel import AnnotationPanel
from ui.label_editor     import LabelEditorDialog

__all__ = [
    "MainWindow",
    "VideoPlayer",
    "AnnotationPanel",
    "LabelEditorDialog",
]