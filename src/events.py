"""
events.py — Rule-based event extraction from sidecar data.
All rules use named thresholds from config.py.
All rules handle None signal values without raising exceptions.
After extraction, re-cuts definitive clips for each confirmed event.
"""
import os
import logging
import uuid
from typing import List, Optional
from collections import defaultdict

from . import config
from . import video_io

log = logging.getLogger(__name__)


def _gen_event_id(event_type: str) -> str:
    """Generate a short unique event ID."""
    short = uuid.uuid4().hex[:6]
    return f"{event_type}_{short}"


def extract_events(
    all_keyframes: List[dict],
    video_paths: dict,
    output_dir: str,
) -> List[dict]:
    """
    Extract events from enriched keyframe data across all videos.

    Args:
        all_keyframes: list of enriched keyframe dicts (from sidecar)
        video_paths: dict mapping filename -> full path
        output_dir: output directory for clips

    Returns:
        List of event dicts
    """
    events = []

    # Group keyframes by video
    by_video = defaultdict(list)
    for kf in all_keyframes:
        by_video[kf["video_file"]].append(kf)

    for video_file, kfs in by_video.items():
        kfs.sort(key=lambda x: x["timestamp_sec"])
        video_path = video_paths.get(video_file)

        # --- Idle Streaks ---
        events.extend(_detect_idle_streaks(kfs, video_file))

        # --- Task Transitions ---
        events.extend(_detect_task_transitions(kfs, video_file))

        # --- Near-Miss Proxy ---
        events.extend(_detect_near_miss(kfs, video_file))

        # --- Occlusion Critical ---
        events.extend(_detect_occlusion_critical(kfs, video_file))

        # --- Approach Hazard Proxy ---
        events.extend(_detect_approach_hazard(kfs, video_file))

        # --- Verification Moments ---
        events.extend(_detect_verification_moments(kfs, video_file))

        # --- Rework Proxy ---
        events.extend(_detect_rework(kfs, video_file))

    # Cut definitive clips for confirmed events
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    for event in events:
        if event.get("video_file") and video_paths.get(event["video_file"]):
            center_sec = (event["start_time_sec"] + event["end_time_sec"]) / 2.0
            clip_path = os.path.join(clips_dir, f"{event['event_id']}.mp4")
            result = video_io.cut_clip(
                video_paths[event["video_file"]],
                center_sec,
                clip_path,
            )
            if result:
                event["evidence"]["clip_path"] = os.path.relpath(clip_path, output_dir)

    log.info(f"Extracted {len(events)} total events across {len(by_video)} videos")
    return events


def _detect_idle_streaks(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect idle_streak events."""
    events = []
    idle_start = None
    idle_start_sec = 0

    for kf in kfs:
        motion = kf.get("motion_magnitude", 0)
        interaction = kf.get("interaction_density", 0)

        if motion is None:
            motion = 0
        if interaction is None:
            interaction = 0

        is_idle = (motion < config.MOTION_THRESH_LOW and
                   interaction < config.INTERACTION_THRESH_LOW)

        if is_idle:
            if idle_start is None:
                idle_start = kf
                idle_start_sec = kf["timestamp_sec"]
        else:
            if idle_start is not None:
                duration = kf["timestamp_sec"] - idle_start_sec
                if duration > config.T_IDLE_SEC:
                    severity = "low"
                    if duration > 120:
                        severity = "high"
                    elif duration > 30:
                        severity = "med"

                    events.append(_make_event(
                        "idle_streak", video_file, idle_start_sec,
                        kf["timestamp_sec"], severity, 0.8,
                        [idle_start.get("frame_path", "")],
                        {"duration_sec": round(duration, 1),
                         "avg_motion": round(motion, 2)},
                    ))
                idle_start = None

    # Handle trailing idle
    if idle_start is not None and len(kfs) > 0:
        duration = kfs[-1]["timestamp_sec"] - idle_start_sec
        if duration > config.T_IDLE_SEC:
            severity = "low" if duration < 30 else ("med" if duration < 120 else "high")
            events.append(_make_event(
                "idle_streak", video_file, idle_start_sec,
                kfs[-1]["timestamp_sec"], severity, 0.8,
                [idle_start.get("frame_path", "")],
                {"duration_sec": round(duration, 1)},
            ))

    return events


def _detect_task_transitions(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect task_transition events from motion spikes + histogram diff."""
    events = []
    if len(kfs) < 3:
        return events

    motions = [kf.get("motion_magnitude", 0) or 0 for kf in kfs]
    mean_motion = sum(motions) / len(motions) if motions else 0
    std_motion = (sum((m - mean_motion) ** 2 for m in motions) / max(len(motions), 1)) ** 0.5

    for kf in kfs:
        motion = kf.get("motion_magnitude", 0) or 0
        hist_diff = kf.get("hist_diff", 0) or 0

        if (motion > mean_motion + 2 * std_motion and
                hist_diff > config.HIST_DIFF_THRESH):
            events.append(_make_event(
                "task_transition", video_file, kf["timestamp_sec"],
                kf["timestamp_sec"] + 2.0, "low", 0.7,
                [kf.get("frame_path", "")],
                {"motion_magnitude": round(motion, 2),
                 "hist_diff": round(hist_diff, 4)},
            ))

    return events


def _detect_near_miss(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect near_miss_proxy events."""
    events = []

    for kf in kfs:
        overlap = kf.get("hand_tool_overlap_pct", 0)
        tool_active = kf.get("tool_active", False)

        if overlap is None:
            overlap = 0
        if tool_active is None:
            tool_active = False

        if overlap > config.NEAR_MISS_OVERLAP_THRESH and tool_active:
            events.append(_make_event(
                "near_miss_proxy", video_file, kf["timestamp_sec"],
                kf["timestamp_sec"] + 2.0, "med", 0.6,
                [kf.get("frame_path", "")],
                {"hand_tool_overlap_pct": overlap,
                 "tool_active": tool_active,
                 "tool_class": kf.get("tool_class")},
            ))

    return events


def _detect_occlusion_critical(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect occlusion_critical events (sustained high overlap during motion)."""
    events = []
    consecutive = 0
    start_kf = None

    for kf in kfs:
        overlap = kf.get("hand_tool_overlap_pct", 0) or 0
        motion = kf.get("motion_magnitude", 0) or 0

        if overlap > config.OCCLUSION_THRESH and motion > config.MOTION_THRESH_HIGH:
            if consecutive == 0:
                start_kf = kf
            consecutive += 1
        else:
            if consecutive >= config.OCCLUSION_MIN_FRAMES and start_kf:
                events.append(_make_event(
                    "occlusion_critical", video_file, start_kf["timestamp_sec"],
                    kf["timestamp_sec"], "high", 0.6,
                    [start_kf.get("frame_path", "")],
                    {"consecutive_frames": consecutive,
                     "max_overlap": overlap},
                ))
            consecutive = 0
            start_kf = None

    return events


def _detect_approach_hazard(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect approach_hazard_proxy events (increasing discontinuity + forward motion)."""
    events = []

    for i in range(config.HAZARD_WINDOW_FRAMES, len(kfs)):
        window = kfs[i - config.HAZARD_WINDOW_FRAMES:i + 1]

        # Check monotonically increasing discontinuity_risk
        disc_risks = []
        for kf in window:
            dr = kf.get("depth_stats", {}).get("discontinuity_risk", 0)
            if dr is None:
                dr = 0
            disc_risks.append(dr)

        increasing = all(disc_risks[j+1] > disc_risks[j]
                         for j in range(len(disc_risks)-1))

        forward = kfs[i].get("forward_motion_proxy", False)
        if forward is None:
            forward = False

        if increasing and forward:
            events.append(_make_event(
                "approach_hazard_proxy", video_file,
                window[0]["timestamp_sec"], window[-1]["timestamp_sec"],
                "med", 0.5,
                [window[-1].get("frame_path", "")],
                {"disc_risk_trend": [round(d, 4) for d in disc_risks]},
            ))

    return events


def _detect_verification_moments(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect verification_moment events (still + hands + stable depth)."""
    events = []
    verify_start = None
    verify_start_sec = 0

    for kf in kfs:
        motion = kf.get("motion_magnitude", 0) or 0
        hands = kf.get("hands_in_workface", False)
        if hands is None:
            hands = False
        depth_var = kf.get("depth_stats", {}).get("variance", 1.0) or 1.0

        is_verify = (motion < config.MOTION_THRESH_LOW and
                     hands and
                     depth_var < config.DEPTH_STABLE_THRESH)

        if is_verify:
            if verify_start is None:
                verify_start = kf
                verify_start_sec = kf["timestamp_sec"]
        else:
            if verify_start is not None:
                duration = kf["timestamp_sec"] - verify_start_sec
                if duration >= config.T_VERIFY_SEC:
                    events.append(_make_event(
                        "verification_moment", video_file,
                        verify_start_sec, kf["timestamp_sec"],
                        "low", 0.7,
                        [verify_start.get("frame_path", "")],
                        {"duration_sec": round(duration, 1)},
                    ))
                verify_start = None

    return events


def _detect_rework(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect rework_proxy events (repeated high interaction in same spatial region)."""
    events = []

    # Track bursts per spatial region
    region_bursts = defaultdict(list)  # region -> list of timestamps

    for kf in kfs:
        interaction = kf.get("interaction_density", 0) or 0
        region = kf.get("spatial_region", 4)

        if interaction > config.INTERACTION_THRESH_HIGH:
            region_bursts[region].append(kf)

    for region, burst_kfs in region_bursts.items():
        if len(burst_kfs) < 3:
            continue

        # Check for clusters within T_REWORK_WINDOW_SEC
        for i in range(len(burst_kfs)):
            window_kfs = [burst_kfs[i]]
            for j in range(i + 1, len(burst_kfs)):
                if (burst_kfs[j]["timestamp_sec"] - burst_kfs[i]["timestamp_sec"]) <= config.T_REWORK_WINDOW_SEC:
                    window_kfs.append(burst_kfs[j])
                else:
                    break

            if len(window_kfs) >= 3:
                events.append(_make_event(
                    "rework_proxy", video_file,
                    window_kfs[0]["timestamp_sec"],
                    window_kfs[-1]["timestamp_sec"],
                    "med", 0.5,
                    [window_kfs[0].get("frame_path", "")],
                    {"spatial_region": region,
                     "burst_count": len(window_kfs)},
                ))
                break  # one event per region

    return events


def _make_event(event_type: str, video_file: str,
                start_sec: float, end_sec: float,
                severity: str, confidence: float,
                keyframe_paths: List[str],
                contributing_signals: dict) -> dict:
    """Create a standard event dict."""
    return {
        "event_id": _gen_event_id(event_type),
        "type": event_type,
        "video_file": video_file,
        "start_time_sec": round(start_sec, 2),
        "end_time_sec": round(end_sec, 2),
        "start_time_fmt": video_io.format_timestamp(start_sec),
        "end_time_fmt": video_io.format_timestamp(end_sec),
        "severity": severity,
        "confidence": round(confidence, 3),
        "llm_grounded": False,
        "evidence": {
            "keyframe_paths": [p for p in keyframe_paths if p],
            "crop_paths": [],
            "clip_path": "",
        },
        "contributing_signals": contributing_signals,
    }
