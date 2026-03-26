"""Global configuration constants."""
import os

# ── Directories ────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR      = os.path.join(BASE_DIR, "output")
FRAMES_DIR      = os.path.join(OUTPUT_DIR, "frames")
LABELS_DIR      = os.path.join(OUTPUT_DIR, "labels")
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov8n.pt")   # auto-downloads if missing

# ── Frame extraction ───────────────────────────────────────────────────────────
DEFAULT_FPS_STEP   = 1        # extract every N-th frame
FRAME_WIDTH        = 640
FRAME_HEIGHT       = 480

# ── YOLO inference ────────────────────────────────────────────────────────────
YOLO_CONFIDENCE    = 0.45
YOLO_IOU_THRESHOLD = 0.45

# ── UI colours ────────────────────────────────────────────────────────────────
BG_DARK   = "#1e1e2e"
BG_PANEL  = "#2a2a3e"
ACCENT    = "#7c6af7"
TEXT_LIGHT= "#e0e0f0"
BOX_COLOR = "#00ff88"          # manual bbox overlay colour

# ── Label storage format ──────────────────────────────────────────────────────
# "yolo"  → YOLO .txt  (class cx cy w h  — normalised)
# "json"  → JSON file per frame
LABEL_FORMAT = "yolo"

for d in (OUTPUT_DIR, FRAMES_DIR, LABELS_DIR):
    os.makedirs(d, exist_ok=True)