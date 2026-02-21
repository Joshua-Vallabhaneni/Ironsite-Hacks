"""
depth.py — Swappable depth estimation backend.
Default: MiDaS via torch.hub.
Normalization: 0.0 = far, 1.0 = close.
"""
import cv2
import logging
import numpy as np
import torch
from typing import Tuple

from . import config

log = logging.getLogger(__name__)

# Module-level model cache
_model = None
_transform = None
_device = None


def _load_midas():
    """Load MiDaS model once via torch.hub."""
    global _model, _transform, _device

    if _model is not None:
        return

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Loading MiDaS on {_device}...")

    # Use MiDaS small for speed (DPT_SwinV2_T_256 is new small)
    # Fallback chain for compatibility
    try:
        _model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True)
        _transform = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True).small_transform
    except Exception:
        try:
            _model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
            _transform = torch.hub.load("intel-isl/MiDaS", "transforms").small_transform
        except Exception as e:
            log.error(f"Failed to load MiDaS: {e}")
            raise

    _model.to(_device)
    _model.eval()
    log.info("MiDaS loaded successfully")


def predict_depth(frame: np.ndarray) -> Tuple[np.ndarray, dict]:
    """
    Predict depth from a BGR frame.

    Returns:
        depth_map: np.ndarray (HxW float32), normalized [0,1]
                   0.0 = far, 1.0 = close
        stats: dict with min, mean, max, variance,
               discontinuity_risk, closest_obstacle
    """
    if config.DEPTH_BACKEND == "midas":
        return _predict_midas(frame)
    else:
        raise ValueError(f"Unknown depth backend: {config.DEPTH_BACKEND}")


def _predict_midas(frame: np.ndarray) -> Tuple[np.ndarray, dict]:
    """MiDaS depth prediction with correct normalization."""
    _load_midas()

    # Convert BGR to RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Apply MiDaS transform
    input_batch = _transform(rgb).to(_device)

    with torch.no_grad():
        prediction = _model(input_batch)
        # Interpolate to original size
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=frame.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

    raw = prediction.cpu().numpy()

    # MiDaS outputs inverse depth (higher = closer)
    # Normalize to [0,1] where 1.0 = close
    depth_min = raw.min()
    depth_max = raw.max()
    depth_normalized = (raw - depth_min) / (depth_max - depth_min + 1e-8)

    # Compute stats
    h, w = depth_normalized.shape

    # Central 50% region for closest_obstacle
    ch1, ch2 = h // 4, 3 * h // 4
    cw1, cw2 = w // 4, 3 * w // 4
    central_region = depth_normalized[ch1:ch2, cw1:cw2]
    closest_obstacle = float(np.percentile(central_region, 90))  # 90th percentile = closest in normalized

    # Lower-center third for discontinuity_risk
    lc_top = 2 * h // 3
    lc_left = w // 3
    lc_right = 2 * w // 3
    lower_center = depth_normalized[lc_top:, lc_left:lc_right]

    # Sobel gradient magnitude on depth
    sobel_x = cv2.Sobel(lower_center, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(lower_center, cv2.CV_64F, 0, 1, ksize=3)
    gradient_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
    discontinuity_risk = float(np.mean(gradient_mag))

    stats = {
        "min": float(depth_normalized.min()),
        "mean": float(depth_normalized.mean()),
        "max": float(depth_normalized.max()),
        "variance": float(np.var(depth_normalized)),
        "discontinuity_risk": round(discontinuity_risk, 4),
        "closest_obstacle": round(closest_obstacle, 4),
    }

    return depth_normalized, stats
