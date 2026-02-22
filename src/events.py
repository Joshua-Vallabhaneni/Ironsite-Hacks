"""
events.py — Rule-based event extraction from sidecar data.
All rules use named thresholds from config.py.
All rules handle None signal values without raising exceptions.
After extraction, re-cuts definitive clips for each confirmed event.
"""
import os
import logging
import uuid
from typing import List
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
        all_keyframes: list of enriched keyframe dicts (from sidecar + activity labels)
        video_paths: dict mapping filename -> full path
        output_dir: output directory for clips

    Returns:
        List of event dicts
    """
    events = []

    by_video = defaultdict(list)
    for kf in all_keyframes:
        by_video[kf["video_file"]].append(kf)

    for video_file, kfs in by_video.items():
        kfs.sort(key=lambda x: x["timestamp_sec"])

        events.extend(_detect_idle_streaks(kfs, video_file))
        events.extend(_detect_task_transitions(kfs, video_file))
        events.extend(_detect_near_miss(kfs, video_file))
        events.extend(_detect_occlusion_critical(kfs, video_file))
        events.extend(_detect_approach_hazard(kfs, video_file))
        events.extend(_detect_verification_moments(kfs, video_file))
        events.extend(_detect_rework(kfs, video_file))
        events.extend(_detect_sustained_work(kfs, video_file))
        events.extend(_detect_ppe_violations(kfs, video_file))

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


# ---------------------------------------------------------------------------
# Idle streaks
# ---------------------------------------------------------------------------

def _detect_idle_streaks(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect idle_streak events: low motion + low interaction sustained > T_IDLE_SEC."""
    events = []
    idle_start = None
    idle_start_sec = 0.0

    for kf in kfs:
        motion = kf.get("motion_magnitude", 0) or 0
        interaction = kf.get("interaction_density", 0) or 0

        # Label-aware: if activity label says idle, treat it as idle regardless of motion
        label = kf.get("gemini_label")
        if (label and label.get("confidence", 0) >= config.ACTIVITY_LABEL_CONF_THRESH
                and label.get("activity") == "idle"):
            is_idle = True
        else:
            is_idle = (motion < config.MOTION_THRESH_LOW
                       and interaction < config.INTERACTION_THRESH_LOW)

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

    # Trailing idle
    if idle_start is not None and kfs:
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


# ---------------------------------------------------------------------------
# Task transitions
# ---------------------------------------------------------------------------

def _detect_task_transitions(kfs: List[dict], video_file: str) -> List[dict]:
    """
    Detect task_transition events.

    Primary path (label-based): fires when Gemini direct labels change between
    work categories (direct / contributory / noncontributory).
    Used when >= 3 direct-labeled frames are available in the video.

    Fallback path (signal-based): motion spike + histogram diff.
    Used when label coverage is insufficient (< 3 direct labels).

    Results are deduplicated and capped per-video.
    """
    if len(kfs) < 3:
        return []

    direct_labeled = [
        kf for kf in kfs
        if (kf.get("gemini_label")
            and not kf["gemini_label"].get("interpolated")
            and kf["gemini_label"].get("confidence", 0) >= config.ACTIVITY_LABEL_CONF_THRESH)
    ]

    if len(direct_labeled) >= 3:
        raw = _label_based_transitions(direct_labeled, video_file)
    else:
        raw = _signal_based_transitions(kfs, video_file)

    return _dedup_task_transitions(raw)


def _label_based_transitions(labeled_kfs: List[dict], video_file: str) -> List[dict]:
    """Detect task transitions from Gemini label category changes."""
    def _category(activity: str) -> str:
        if activity in config.ACTIVITY_DIRECT_WORK:
            return "direct"
        if activity in config.ACTIVITY_CONTRIBUTORY:
            return "contributory"
        return "noncontributory"

    raw = []
    prev_category = None
    prev_activity = None

    for kf in labeled_kfs:
        activity = kf["gemini_label"].get("activity", "other")
        category = _category(activity)

        if prev_category is not None and category != prev_category:
            raw.append(_make_event(
                "task_transition", video_file, kf["timestamp_sec"],
                kf["timestamp_sec"] + 2.0, "low", 0.75,
                [kf.get("frame_path", "")],
                {
                    "trigger": "label",
                    "from_activity": prev_activity,
                    "to_activity": activity,
                    "from_category": prev_category,
                    "to_category": category,
                },
            ))

        prev_category = category
        prev_activity = activity

    return raw


def _signal_based_transitions(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect task transitions from motion spikes + histogram diff (fallback)."""
    motions = [kf.get("motion_magnitude", 0) or 0 for kf in kfs]
    mean_motion = sum(motions) / len(motions) if motions else 0
    variance = sum((m - mean_motion) ** 2 for m in motions) / max(len(motions), 1)
    std_motion = variance ** 0.5

    raw = []
    for kf in kfs:
        motion = kf.get("motion_magnitude", 0) or 0
        hist_diff = kf.get("hist_diff", 0) or 0

        if (motion > mean_motion + 2 * std_motion
                and hist_diff > config.HIST_DIFF_THRESH):
            raw.append(_make_event(
                "task_transition", video_file, kf["timestamp_sec"],
                kf["timestamp_sec"] + 2.0, "low", 0.7,
                [kf.get("frame_path", "")],
                {
                    "trigger": "signal",
                    "motion_magnitude": round(motion, 2),
                    "hist_diff": round(hist_diff, 4),
                },
            ))

    return raw


def _dedup_task_transitions(transitions: List[dict]) -> List[dict]:
    """
    Merge transitions within MIN_TRANSITION_GAP_SEC of each other.
    Cap result at MAX_TRANSITIONS_PER_VIDEO.
    """
    if not transitions:
        return []

    transitions.sort(key=lambda e: e["start_time_sec"])
    merged = [transitions[0]]

    for t in transitions[1:]:
        last = merged[-1]
        gap = t["start_time_sec"] - last["end_time_sec"]
        if gap < config.MIN_TRANSITION_GAP_SEC:
            # Extend end time of current group
            merged[-1]["end_time_sec"] = max(last["end_time_sec"], t["end_time_sec"])
            merged[-1]["end_time_fmt"] = video_io.format_timestamp(merged[-1]["end_time_sec"])
        else:
            merged.append(t)

    return merged[: config.MAX_TRANSITIONS_PER_VIDEO]


# ---------------------------------------------------------------------------
# Near-miss proxy
# ---------------------------------------------------------------------------

def _detect_near_miss(kfs: List[dict], video_file: str) -> List[dict]:
    """
    Detect near_miss_proxy events.

    Two trigger paths:
      1. Label-based (primary): tool held + high-risk posture + active work activity.
         Only fires on direct (non-interpolated) labels with >= 30s cooldown.
      2. Signal-based (fallback): hand_tool_overlap + tool_active (for rules_only mode).
    """
    events = []
    last_event_sec = -999.0
    COOLDOWN = 30.0

    for kf in kfs:
        label = kf.get("gemini_label")
        triggered = False
        signals = {}

        # Path 1: label-based (direct labels only, not interpolated)
        if (label
                and label.get("confidence", 0) >= config.ACTIVITY_LABEL_CONF_THRESH
                and not label.get("interpolated")):
            tool = label.get("tool_held", "unknown")
            posture = label.get("posture", "other")
            activity = label.get("activity", "other")
            if (tool not in ("none", "unknown")
                    and posture in config.NEAR_MISS_HIGH_RISK_POSTURES
                    and activity in config.NEAR_MISS_ACTIVE_ACTIVITIES):
                triggered = True
                signals = {
                    "trigger": "label",
                    "tool_held": tool,
                    "posture": posture,
                    "activity": activity,
                }

        # Path 2: signal-based fallback (when label path not triggered)
        if not triggered:
            overlap = kf.get("hand_tool_overlap_pct", 0) or 0
            tool_active = kf.get("tool_active", False) or False
            if overlap > config.NEAR_MISS_OVERLAP_THRESH and tool_active:
                triggered = True
                signals = {
                    "trigger": "signal",
                    "hand_tool_overlap_pct": overlap,
                    "tool_active": tool_active,
                    "tool_class": kf.get("tool_class"),
                }

        if triggered and (kf["timestamp_sec"] - last_event_sec) >= COOLDOWN:
            events.append(_make_event(
                "near_miss_proxy", video_file, kf["timestamp_sec"],
                kf["timestamp_sec"] + 2.0, "med", 0.6,
                [kf.get("frame_path", "")],
                signals,
            ))
            last_event_sec = kf["timestamp_sec"]

    return events


# ---------------------------------------------------------------------------
# Occlusion critical
# ---------------------------------------------------------------------------

def _detect_occlusion_critical(kfs: List[dict], video_file: str) -> List[dict]:
    """
    Detect occlusion_critical events.

    Two trigger paths:
      1. Depth-based (primary): high discontinuity_risk + high interaction_density
         sustained for >= OCCLUSION_MIN_FRAMES consecutive frames.
      2. Signal-based (fallback): high hand_tool_overlap + high motion.
    """
    events = []
    consecutive = 0
    start_kf = None
    trigger_type = "signal"

    for kf in kfs:
        overlap = kf.get("hand_tool_overlap_pct", 0) or 0
        motion = kf.get("motion_magnitude", 0) or 0
        disc_risk = kf.get("depth_stats", {}).get("discontinuity_risk", 0) or 0
        interaction = kf.get("interaction_density", 0) or 0

        depth_trigger = (disc_risk > config.DEPTH_HAZARD_DISC_RISK_THRESH
                         and interaction > config.INTERACTION_THRESH_HIGH)
        signal_trigger = (overlap > config.OCCLUSION_THRESH
                          and motion > config.MOTION_THRESH_HIGH)

        if depth_trigger or signal_trigger:
            if consecutive == 0:
                start_kf = kf
                trigger_type = "depth" if depth_trigger else "signal"
            consecutive += 1
        else:
            if consecutive >= config.OCCLUSION_MIN_FRAMES and start_kf:
                events.append(_make_event(
                    "occlusion_critical", video_file, start_kf["timestamp_sec"],
                    kf["timestamp_sec"], "high", 0.6,
                    [start_kf.get("frame_path", "")],
                    {"consecutive_frames": consecutive,
                     "trigger": trigger_type,
                     "max_disc_risk": round(disc_risk, 3)},
                ))
            consecutive = 0
            start_kf = None

    # Trailing sequence
    if consecutive >= config.OCCLUSION_MIN_FRAMES and start_kf and kfs:
        events.append(_make_event(
            "occlusion_critical", video_file, start_kf["timestamp_sec"],
            kfs[-1]["timestamp_sec"], "high", 0.6,
            [start_kf.get("frame_path", "")],
            {"consecutive_frames": consecutive, "trigger": trigger_type},
        ))

    return events


# ---------------------------------------------------------------------------
# Approach hazard proxy
# ---------------------------------------------------------------------------

def _detect_approach_hazard(kfs: List[dict], video_file: str) -> List[dict]:
    """Detect approach_hazard_proxy events (increasing discontinuity + forward motion)."""
    events = []

    for i in range(config.HAZARD_WINDOW_FRAMES, len(kfs)):
        window = kfs[i - config.HAZARD_WINDOW_FRAMES : i + 1]

        disc_risks = []
        for kf in window:
            dr = kf.get("depth_stats", {}).get("discontinuity_risk", 0) or 0
            disc_risks.append(dr)

        increasing = all(
            disc_risks[j + 1] > disc_risks[j] for j in range(len(disc_risks) - 1)
        )
        forward = kfs[i].get("forward_motion_proxy", False) or False

        if increasing and forward:
            events.append(_make_event(
                "approach_hazard_proxy", video_file,
                window[0]["timestamp_sec"], window[-1]["timestamp_sec"],
                "med", 0.5,
                [window[-1].get("frame_path", "")],
                {"disc_risk_trend": [round(d, 4) for d in disc_risks]},
            ))

    return events


# ---------------------------------------------------------------------------
# Verification moments
# ---------------------------------------------------------------------------

def _detect_verification_moments(kfs: List[dict], video_file: str) -> List[dict]:
    """
    Detect verification_moment events.

    Two trigger paths:
      1. Signal-based: low motion + hands_in_workface + stable depth
      2. Label-based (more permissive): activity=measuring or inspection
         with motion below MOTION_THRESH_HIGH * 1.5
    """
    events = []
    verify_start = None
    verify_start_sec = 0.0

    for kf in kfs:
        motion = kf.get("motion_magnitude", 0) or 0
        hands = kf.get("hands_in_workface", False) or False
        depth_var = kf.get("depth_stats", {}).get("variance", 1.0) or 1.0
        label = kf.get("gemini_label")

        # Path 1: signal-based
        signal_verify = (
            motion < config.MOTION_THRESH_LOW
            and hands
            and depth_var < config.DEPTH_STABLE_THRESH
        )

        # Path 2: label-based (measuring or inspection activity)
        label_verify = False
        if label and label.get("confidence", 0) >= config.ACTIVITY_LABEL_CONF_THRESH:
            if label.get("activity") in ("measuring", "inspection"):
                label_verify = motion < config.MOTION_THRESH_HIGH * 1.5

        is_verify = signal_verify or label_verify

        if is_verify:
            if verify_start is None:
                verify_start = kf
                verify_start_sec = kf["timestamp_sec"]
        else:
            if verify_start is not None:
                duration = kf["timestamp_sec"] - verify_start_sec
                if duration >= config.T_VERIFY_SEC:
                    trigger = "label" if label_verify else "signal"
                    events.append(_make_event(
                        "verification_moment", video_file,
                        verify_start_sec, kf["timestamp_sec"],
                        "low", 0.7,
                        [verify_start.get("frame_path", "")],
                        {"duration_sec": round(duration, 1), "trigger": trigger},
                    ))
                verify_start = None

    return events


# ---------------------------------------------------------------------------
# Rework proxy
# ---------------------------------------------------------------------------

def _detect_rework(kfs: List[dict], video_file: str) -> List[dict]:
    """
    Detect rework_proxy events (worker returning to same spatial region after a gap).

    Groups high-interaction frames into bursts (consecutive frames within
    REWORK_BURST_GAP_SEC of each other). A rework event fires only when the same
    region has >= 2 distinct bursts separated by >= REWORK_MIN_GAP_SEC, indicating
    the worker left and returned to redo work — not just sustained work in one place.
    """
    events = []
    region_high_kfs = defaultdict(list)

    for kf in kfs:
        interaction = kf.get("interaction_density", 0) or 0
        region = kf.get("spatial_region", 4)

        if interaction > config.INTERACTION_THRESH_HIGH:
            region_high_kfs[region].append(kf)

    for region, hi_kfs in region_high_kfs.items():
        if len(hi_kfs) < 2:
            continue

        hi_kfs.sort(key=lambda x: x["timestamp_sec"])

        # Group frames into bursts (max REWORK_BURST_GAP_SEC between consecutive frames)
        bursts = []
        cur_burst = [hi_kfs[0]]
        for i in range(1, len(hi_kfs)):
            gap = hi_kfs[i]["timestamp_sec"] - hi_kfs[i - 1]["timestamp_sec"]
            if gap <= config.REWORK_BURST_GAP_SEC:
                cur_burst.append(hi_kfs[i])
            else:
                bursts.append(cur_burst)
                cur_burst = [hi_kfs[i]]
        bursts.append(cur_burst)

        if len(bursts) < 2:
            continue

        # Find first pair of bursts with a gap >= REWORK_MIN_GAP_SEC between them
        for i in range(len(bursts) - 1):
            gap_between = bursts[i + 1][0]["timestamp_sec"] - bursts[i][-1]["timestamp_sec"]
            if gap_between >= config.REWORK_MIN_GAP_SEC:
                start_kf = bursts[i][0]
                end_kf = bursts[i + 1][-1]
                events.append(_make_event(
                    "rework_proxy", video_file,
                    start_kf["timestamp_sec"],
                    end_kf["timestamp_sec"],
                    "med", 0.55,
                    [start_kf.get("frame_path", "")],
                    {
                        "spatial_region": region,
                        "burst_count": 2,
                        "gap_sec": round(gap_between, 1),
                    },
                ))
                break  # one event per region

    return events


# ---------------------------------------------------------------------------
# Sustained work
# ---------------------------------------------------------------------------

def _detect_sustained_work(kfs: List[dict], video_file: str) -> List[dict]:
    """
    Detect sustained_work events: continuous high-interaction activity for
    >= T_SUSTAINED_WORK_SEC seconds.

    Uses Gemini labels when available; falls back to interaction_density signal.
    This is a positive indicator used for productivity and quality reporting.
    """
    events = []
    work_start = None
    work_start_sec = 0.0
    work_activity = "active"

    for kf in kfs:
        interaction = kf.get("interaction_density", 0) or 0
        label = kf.get("gemini_label")

        # Determine if this frame is active work
        is_work = False
        current_activity = "active"

        if label and label.get("confidence", 0) >= config.ACTIVITY_LABEL_CONF_THRESH:
            activity = label.get("activity", "other")
            if activity in config.ACTIVITY_DIRECT_WORK:
                is_work = True
                current_activity = activity
        if not is_work and interaction > config.INTERACTION_THRESH_HIGH:
            is_work = True

        if is_work:
            if work_start is None:
                work_start = kf
                work_start_sec = kf["timestamp_sec"]
                work_activity = current_activity
        else:
            if work_start is not None:
                duration = kf["timestamp_sec"] - work_start_sec
                if duration >= config.T_SUSTAINED_WORK_SEC:
                    severity = "low"
                    if duration > 600:
                        severity = "high"
                    elif duration > 300:
                        severity = "med"
                    events.append(_make_event(
                        "sustained_work", video_file,
                        work_start_sec, kf["timestamp_sec"],
                        severity, 0.75,
                        [work_start.get("frame_path", "")],
                        {"duration_sec": round(duration, 1),
                         "primary_activity": work_activity},
                    ))
                work_start = None

    # Trailing work segment
    if work_start is not None and kfs:
        duration = kfs[-1]["timestamp_sec"] - work_start_sec
        if duration >= config.T_SUSTAINED_WORK_SEC:
            severity = "low" if duration < 300 else ("med" if duration < 600 else "high")
            events.append(_make_event(
                "sustained_work", video_file,
                work_start_sec, kfs[-1]["timestamp_sec"],
                severity, 0.75,
                [work_start.get("frame_path", "")],
                {"duration_sec": round(duration, 1),
                 "primary_activity": work_activity},
            ))

    return events


# ---------------------------------------------------------------------------
# PPE violations
# ---------------------------------------------------------------------------

def _detect_ppe_violations(kfs: List[dict], video_file: str) -> List[dict]:
    """
    Detect ppe_violation events from Gemini activity labels.

    Fires when protective gloves are explicitly absent (False, not "uncertain")
    during active hand work (brick_laying, mortar_application, material_handling,
    measuring). This avoids the false-positive flood caused by checking ppe_hard_hat,
    which is physically impossible to observe in egocentric (helmet-cam) footage —
    the camera IS the hard hat.

    Only runs when Gemini labels are present.
    """
    events = []
    violation_start = None
    violation_start_sec = 0.0

    for kf in kfs:
        label = kf.get("gemini_label")

        if not label:
            # No label — close any open violation streak
            if violation_start is not None:
                events.append(_make_ppe_event(
                    video_file, violation_start_sec, kf["timestamp_sec"], violation_start
                ))
                violation_start = None
            continue

        # Skip uncertain or low-confidence labels
        if label.get("confidence", 0) < config.ACTIVITY_LABEL_CONF_THRESH:
            continue

        activity = label.get("activity", "other")
        gloves = label.get("ppe_gloves")
        is_active_work = activity in config.PPE_ACTIVE_ACTIVITIES

        # Only flag missing gloves during active hand work
        if is_active_work and gloves is False:
            if violation_start is None:
                violation_start = kf
                violation_start_sec = kf["timestamp_sec"]
        else:
            if violation_start is not None:
                events.append(_make_ppe_event(
                    video_file, violation_start_sec, kf["timestamp_sec"], violation_start
                ))
                violation_start = None

    # Trailing violation
    if violation_start is not None and kfs:
        events.append(_make_ppe_event(
            video_file, violation_start_sec, kfs[-1]["timestamp_sec"], violation_start
        ))

    return events


def _make_ppe_event(
    video_file: str, start_sec: float, end_sec: float, start_kf: dict
) -> dict:
    """Create a ppe_violation event dict."""
    duration = max(0.0, end_sec - start_sec)
    return _make_event(
        "ppe_violation", video_file, start_sec, end_sec,
        "high", 0.75,
        [start_kf.get("frame_path", "")],
        {"violation_type": "missing_gloves",
         "duration_sec": round(duration, 1)},
    )


# ---------------------------------------------------------------------------
# Shared factory
# ---------------------------------------------------------------------------

def _make_event(
    event_type: str,
    video_file: str,
    start_sec: float,
    end_sec: float,
    severity: str,
    confidence: float,
    keyframe_paths: List[str],
    contributing_signals: dict,
) -> dict:
    """Create a standard event dict."""
    return {
        "event_id":              _gen_event_id(event_type),
        "type":                  event_type,
        "video_file":            video_file,
        "start_time_sec":        round(start_sec, 2),
        "end_time_sec":          round(end_sec, 2),
        "start_time_fmt":        video_io.format_timestamp(start_sec),
        "end_time_fmt":          video_io.format_timestamp(end_sec),
        "severity":              severity,
        "confidence":            round(confidence, 3),
        "llm_grounded":          False,
        "evidence": {
            "keyframe_paths": [p for p in keyframe_paths if p],
            "crop_paths":     [],
            "clip_path":      "",
        },
        "contributing_signals": contributing_signals,
    }
