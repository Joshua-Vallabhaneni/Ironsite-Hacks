"""
config.py — ALL thresholds, backend flags, budgets, and constants.
No magic numbers anywhere else in the codebase.
"""
import os

# ─── Depth Backend ──────────────────────────────────────────
DEPTH_BACKEND = os.environ.get("DEPTH_BACKEND", "midas")  # "midas" or "dav2"

# ─── Frame Sampling ─────────────────────────────────────────
SAMPLE_EVERY_SEC = 2.0          # uniform sampling interval
MOTION_THRESH_HIGH = 15.0       # motion magnitude for motion-biased oversampling
MOTION_THRESH_LOW = 3.0         # below this = near-static
HIST_DIFF_THRESH = 0.35         # chi-square threshold for scene transition

# ─── Event Windows ───────────────────────────────────────────
EVENT_WINDOW_SEC = 4.0          # ±4 seconds around detected events for clip cutting

# ─── Detection ───────────────────────────────────────────────
HAND_CONF_THRESH = 0.5          # MediaPipe hand confidence threshold
YOLO_CONF_THRESH = 0.3          # YOLOv8 detection confidence
YOLO_MODEL = "yolov8n.pt"       # YOLOv8 nano for speed

# ─── Interaction & Sidecar ───────────────────────────────────
INTERACTION_THRESH_LOW = 0.25
INTERACTION_THRESH_HIGH = 0.65
DEPTH_WINDOW_FRAMES = 5         # rolling window for forward_motion_proxy
DEPTH_STABLE_THRESH = 0.02      # depth variance threshold for verification moments

# ─── Event Extraction ───────────────────────────────────────
T_IDLE_SEC = 10.0               # seconds of low activity to count as idle
T_LONG_IDLE_SEC = 120.0         # long idle threshold for productivity penalty
T_VERIFY_SEC = 3.0              # seconds of still+hands for verification moment
T_REWORK_WINDOW_SEC = 120.0     # window for repeated spatial-region activity
T_ERGONOMIC_MIN = 5.0           # minutes of continuous high motion for ergonomic flag
NEAR_MISS_OVERLAP_THRESH = 0.3  # IOU for near-miss proxy
OCCLUSION_THRESH = 0.5          # IOU for occlusion-critical
OCCLUSION_MIN_FRAMES = 3        # consecutive frames for occlusion event
HAZARD_WINDOW_FRAMES = 4        # frames for approach-hazard detection
TOOL_RECURRENCE_WINDOW = 3      # last N keyframes for tool_active check

# ─── Spatial Query ───────────────────────────────────────────
SPATIAL_QUERY_K = 20            # top-K events for spatial query
SPATIAL_QUERY_TIMEOUT = 10      # seconds per Gemini call
SPATIAL_QUERY_MIN_CONF = 0.5    # minimum bbox confidence for crop+re-query

# ─── Gemini Budgets ──────────────────────────────────────────
GEMINI_BUDGET = 200             # augmented mode budget
GEMINI_BUDGET_BASELINE = 100    # baseline mode budget
GEMINI_MODEL = "gemini-2.5-flash"

# ─── Baseline Mode ───────────────────────────────────────────
BASELINE_MAX_FRAMES = 200       # total frames across all videos for baseline
BASELINE_CHUNK_SIZE = 20        # frames per chunk for baseline Gemini calls

# ─── Output ──────────────────────────────────────────────────
FRAME_SAVE_SIZE = (640, 480)    # saved keyframe resolution
CROP_PADDING = 0.1              # padding around crop bboxes (fraction)
CLIP_FPS = 15                   # output clip framerate
MAX_CLIP_DURATION = 12          # max ±4s = 8s, add buffer
