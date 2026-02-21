"""
sidecar.py — Assembles per-frame features and temporal proxies.
Produces the spatiotemporal evidence sidecar that constrains Gemini's reporting.
"""
import os
import cv2
import json
import logging
import numpy as np
from typing import List, Optional

from . import config
from . import video_io
from . import scene_select
from . import depth as depth_module
from . import detect as detect_module

log = logging.getLogger(__name__)


def build_sidecar_for_video(
    video_path: str,
    video_info: dict,
    keyframes: List[dict],
    output_dir: str,
) -> List[dict]:
    """
    Build per-frame sidecar features for a video's keyframes.

    For each keyframe:
    1. Extract frame from video
    2. Run depth estimation
    3. Run hand + object detection
    4. Compute composite features
    5. Save keyframe image

    Returns list of enriched keyframe dicts.
    """
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    enriched = []
    depth_history = []  # rolling depth means for forward_motion_proxy
    recent_tool_detections = []  # last N for tool_active

    for i, kf in enumerate(keyframes):
        # Extract frame
        frame = video_io.extract_frame_at_time(video_path, kf["timestamp_sec"])
        if frame is None:
            log.warning(f"Could not extract frame at {kf['timestamp_sec']}s, skipping")
            continue

        # Save keyframe
        frame_path = os.path.join(frames_dir, f"{kf['frame_id']}.jpg")
        video_io.save_frame(frame, frame_path, config.FRAME_SAVE_SIZE)

        # Depth estimation
        try:
            depth_map, depth_stats = depth_module.predict_depth(frame)
        except Exception as e:
            log.warning(f"Depth estimation failed for {kf['frame_id']}: {e}")
            depth_map = None
            depth_stats = {
                "min": 0, "mean": 0.5, "max": 1.0,
                "variance": 0, "discontinuity_risk": 0, "closest_obstacle": 0.5,
            }

        # Hand detection
        hand_result = detect_module.detect_hands(frame)

        # Object detection
        obj_result = detect_module.detect_objects(frame)

        # If hand uncertain, try to use person bbox as fallback
        hand_bbox = hand_result["hand_bbox"]
        hand_present = hand_result["hand_present"]
        if hand_present is None and obj_result["person_present"] and obj_result["person_bbox"]:
            # Use lower portion of person bbox as rough hand region proxy
            pbbox = obj_result["person_bbox"]
            hand_bbox = [pbbox[0], pbbox[1] + pbbox[3] * 0.6, pbbox[2], pbbox[3] * 0.4]

        # Compute features
        motion_mag = kf.get("motion_magnitude", 0.0)

        # tool_active: tool present + high motion + recurrence
        recent_tool_detections.append(obj_result["tool_present"])
        if len(recent_tool_detections) > config.TOOL_RECURRENCE_WINDOW:
            recent_tool_detections = recent_tool_detections[-config.TOOL_RECURRENCE_WINDOW:]

        tool_recurrence = sum(recent_tool_detections[-config.TOOL_RECURRENCE_WINDOW:])
        tool_active = (
            obj_result["tool_present"]
            and motion_mag > config.MOTION_THRESH_HIGH
            and tool_recurrence >= 2
        )

        # hand_tool_overlap_pct
        hand_tool_overlap = detect_module.compute_iou(hand_bbox, obj_result["tool_bbox"])

        # hands_in_workface
        hands_in_workface = detect_module.is_in_workface(hand_bbox)

        # interaction_density
        hand_score = 1.0 if hand_present is True else (0.5 if hand_present is None else 0.0)
        tool_score = 1.0 if obj_result["tool_present"] else 0.0
        motion_norm = min(motion_mag / max(config.MOTION_THRESH_HIGH, 1e-8), 1.0)
        interaction_density = (hand_score + tool_score + motion_norm) / 3.0

        # occlusion_proxy
        occlusion_proxy = hand_tool_overlap

        # downtime_proxy (initial — sustained check happens in events.py)
        downtime_proxy = (
            motion_mag < config.MOTION_THRESH_LOW
            and hand_present is not True
            and not obj_result["tool_present"]
        )

        # forward_motion_proxy — rolling depth check
        depth_history.append(depth_stats["mean"])
        if len(depth_history) > config.DEPTH_WINDOW_FRAMES:
            depth_history = depth_history[-config.DEPTH_WINDOW_FRAMES:]

        forward_motion_proxy = False
        if len(depth_history) >= config.DEPTH_WINDOW_FRAMES:
            # Check if mean depth increasing (closer objects → higher values)
            diffs = [depth_history[j+1] - depth_history[j]
                     for j in range(len(depth_history)-1)]
            forward_motion_proxy = all(d > 0 for d in diffs)

        # spatial_region
        primary_bbox = hand_bbox if hand_bbox else obj_result["tool_bbox"]
        spatial_region = detect_module.get_spatial_region(primary_bbox)

        # Build enriched keyframe
        enriched_kf = {
            **kf,
            "frame_path": os.path.relpath(frame_path, output_dir),
            # Depth
            "depth_stats": depth_stats,
            # Detection
            "hand_present": hand_present,
            "hand_confidence": hand_result["hand_confidence"],
            "hand_bbox": [round(v, 4) for v in hand_bbox] if hand_bbox else None,
            "tool_present": obj_result["tool_present"],
            "tool_class": obj_result["tool_class"],
            "tool_bbox": obj_result["tool_bbox"],
            "tool_confidence": obj_result["tool_confidence"],
            "tool_active": tool_active,
            "all_detections": obj_result["all_detections"],
            # Composite features
            "hand_tool_overlap_pct": round(hand_tool_overlap, 4),
            "hands_in_workface": hands_in_workface,
            "interaction_density": round(interaction_density, 4),
            "occlusion_proxy": round(occlusion_proxy, 4),
            "downtime_proxy": downtime_proxy,
            "forward_motion_proxy": forward_motion_proxy,
            "spatial_region": spatial_region,
        }

        enriched.append(enriched_kf)

        if (i + 1) % 50 == 0:
            log.info(f"  Processed {i+1}/{len(keyframes)} keyframes for {video_info['filename']}")

    log.info(f"Built sidecar for {video_info['filename']}: {len(enriched)} frames")
    return enriched


def save_sidecar(sidecar_data: dict, output_dir: str) -> str:
    """Save complete sidecar JSON."""
    path = os.path.join(output_dir, "sidecar.json")
    with open(path, "w") as f:
        json.dump(sidecar_data, f, indent=2, default=str)
    log.info(f"Saved sidecar to {path}")
    return path
