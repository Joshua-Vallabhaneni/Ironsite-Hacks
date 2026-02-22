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

# ─── Activity Labeling (Phase 2.5) ───────────────────────────────────────────────────────────────────
ACTIVITY_LABEL_INTERVAL_SEC = 30.0   # label 1 uniform frame per 30s per video
ACTIVITY_LABEL_BATCH_SIZE = 4        # frames per Gemini call (smaller = less output token pressure)
ACTIVITY_LABEL_CONF_THRESH = 0.6     # min label confidence to override signals
ACTIVITY_LABEL_INTERP_SEC = 20.0     # propagate label to frames within +/-20s

# Activity -> interaction_density override mapping
ACTIVITY_INTERACTION_MAP = {
    "brick_laying":        0.85,
    "mortar_application":  0.85,
    "material_handling":   0.65,
    "scaffolding":         0.60,
    "measuring":           0.55,
    "inspection":          0.50,
    "other":               0.35,
    "repositioning":       0.30,
    "idle":                0.10,
}

# Productivity classification buckets
ACTIVITY_DIRECT_WORK     = frozenset({"brick_laying", "mortar_application",
                                       "material_handling", "scaffolding"})
ACTIVITY_CONTRIBUTORY    = frozenset({"measuring", "inspection", "repositioning", "other"})
ACTIVITY_NONCONTRIBUTORY = frozenset({"idle"})

# ─── Sustained Work Event ────────────────────────────────────────────────────────────────────────────
T_SUSTAINED_WORK_SEC = 60.0          # min duration to fire a sustained_work event

# ─── Task Transition Deduplication ───────────────────────────────────────────────────────────────────
MIN_TRANSITION_GAP_SEC = 30.0        # merge transitions closer than this
MAX_TRANSITIONS_PER_VIDEO = 10       # hard cap per video after deduplication

# ─── Rework Detection ────────────────────────────────────────────────────────────────────────────
REWORK_MIN_GAP_SEC = 60.0            # min gap between work bursts to qualify as rework
REWORK_BURST_GAP_SEC = 30.0          # max consecutive-frame gap within a single burst

# ─── Near-Miss Detection (label-based path) ──────────────────────────────────────────────────────
NEAR_MISS_HIGH_RISK_POSTURES = frozenset({"crouching", "reaching_overhead"})
NEAR_MISS_ACTIVE_ACTIVITIES = frozenset({
    "brick_laying", "mortar_application", "material_handling", "measuring",
})

# ─── PPE Glove Detection ─────────────────────────────────────────────────────────────────────────
# Hard hat is on the camera in egocentric footage — never visible. Track gloves instead.
PPE_ACTIVE_ACTIVITIES = frozenset({
    "brick_laying", "mortar_application", "material_handling", "measuring",
})

# ─── Occlusion / Depth Hazard ────────────────────────────────────────────────────────────────────
DEPTH_HAZARD_DISC_RISK_THRESH = 0.75  # discontinuity_risk threshold for occlusion detection
