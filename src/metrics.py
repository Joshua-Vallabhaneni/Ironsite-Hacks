"""
metrics.py — Four indices (Safety, Ergonomics, Productivity, Quality)
Each deduction cites at least one event_id. All indices floor at 0.
"""
import logging
from typing import List, Dict
from collections import defaultdict

from . import config

log = logging.getLogger(__name__)


def compute_all_metrics(events: List[dict], all_keyframes: List[dict]) -> dict:
    """
    Compute all four indices from events and keyframes.

    Returns dict with safety, ergonomics, productivity, quality indices
    and detailed breakdowns with event citations.
    """
    safety = compute_safety_index(events)
    ergonomics = compute_ergonomics_index(events, all_keyframes)
    productivity = compute_productivity_index(events, all_keyframes)
    quality = compute_quality_index(events)

    return {
        "safety": safety,
        "ergonomics": ergonomics,
        "productivity": productivity,
        "quality": quality,
    }


def compute_safety_index(events: List[dict]) -> dict:
    """
    Safety Index (starts at 100):
    - −15 per high severity near_miss or occlusion_critical
    - −8 per med severity
    - −3 per low severity
    - −5 per approach_hazard_proxy event
    - −1 per minute of cumulative high-risk exposure
    """
    score = 100
    deductions = []

    safety_events = [e for e in events
                     if e["type"] in ("near_miss_proxy", "occlusion_critical", "approach_hazard_proxy")]

    cumulative_risk_sec = 0

    for event in safety_events:
        sev = event.get("severity", "low")
        etype = event["type"]
        eid = event["event_id"]

        if etype in ("near_miss_proxy", "occlusion_critical"):
            if sev == "high":
                penalty = 15
            elif sev == "med":
                penalty = 8
            else:
                penalty = 3
            score -= penalty
            deductions.append({
                "event_id": eid,
                "reason": f"{etype} ({sev})",
                "penalty": -penalty,
            })

            # Accumulate risk time
            duration = event.get("end_time_sec", 0) - event.get("start_time_sec", 0)
            cumulative_risk_sec += max(0, duration)

        elif etype == "approach_hazard_proxy":
            score -= 5
            deductions.append({
                "event_id": eid,
                "reason": f"approach_hazard_proxy",
                "penalty": -5,
            })
            duration = event.get("end_time_sec", 0) - event.get("start_time_sec", 0)
            cumulative_risk_sec += max(0, duration)

    # -1 per minute of risk exposure
    risk_minutes = cumulative_risk_sec / 60.0
    if risk_minutes > 0:
        time_penalty = int(risk_minutes)
        score -= time_penalty
        if time_penalty > 0:
            deductions.append({
                "event_id": "cumulative",
                "reason": f"{risk_minutes:.1f} min cumulative risk exposure",
                "penalty": -time_penalty,
            })

    score = max(0, score)

    return {
        "score": score,
        "deductions": deductions,
        "event_count": len(safety_events),
    }


def compute_ergonomics_index(events: List[dict], all_keyframes: List[dict]) -> dict:
    """
    Ergonomics Index (starts at 100):
    - −10 per continuous high-motion manipulation > T_ERGONOMIC_MIN minutes
    - −5 per rapid repeated high-interaction burst cluster
    """
    score = 100
    deductions = []

    # Find continuous high-motion segments
    high_motion_segments = []
    seg_start = None
    seg_start_sec = 0.0

    for kf in all_keyframes:
        motion = kf.get("motion_magnitude", 0) or 0
        interaction = kf.get("interaction_density", 0) or 0

        if motion > config.MOTION_THRESH_HIGH and interaction > config.INTERACTION_THRESH_HIGH:
            if seg_start is None:
                seg_start = kf
                seg_start_sec = kf["timestamp_sec"]
        else:
            if seg_start is not None:
                duration_min = (kf["timestamp_sec"] - seg_start_sec) / 60.0
                if duration_min > config.T_ERGONOMIC_MIN:
                    high_motion_segments.append({
                        "start": seg_start_sec,
                        "end": kf["timestamp_sec"],
                        "duration_min": duration_min,
                        "frame_id": seg_start.get("frame_id", ""),
                    })
                seg_start = None

    for seg in high_motion_segments:
        score -= 10
        deductions.append({
            "event_id": seg.get("frame_id", "segment"),
            "reason": f"Continuous high-motion manipulation ({seg['duration_min']:.1f} min)",
            "penalty": -10,
        })

    # Rework events as ergonomic repetitive motion
    rework_events = [e for e in events if e["type"] == "rework_proxy"]
    for event in rework_events:
        score -= 5
        deductions.append({
            "event_id": event["event_id"],
            "reason": "Repetitive motion cluster (rework_proxy)",
            "penalty": -5,
        })

    score = max(0, score)

    return {
        "score": score,
        "deductions": deductions,
        "high_motion_segments": len(high_motion_segments),
    }


def compute_productivity_index(events: List[dict], all_keyframes: List[dict]) -> dict:
    """
    Productivity Index:
    = 100 × (direct_work_min + 0.5 × contributory_min) / total_analyzed_min
    + penalties for long idles
    """
    if not all_keyframes:
        return {"score": 0, "direct_min": 0, "contributory_min": 0,
                "noncontributory_min": 0, "total_min": 0, "deductions": []}

    # Classify each keyframe
    direct_count = 0
    contributory_count = 0
    noncontributory_count = 0

    # Get idle event timestamps for noncontributory classification
    idle_events = [e for e in events if e["type"] == "idle_streak"]
    idle_ranges = [(e["start_time_sec"], e["end_time_sec"]) for e in idle_events]

    for kf in all_keyframes:
        ts = kf["timestamp_sec"]
        interaction = kf.get("interaction_density", 0) or 0
        motion = kf.get("motion_magnitude", 0) or 0

        # Check if in idle range
        in_idle = any(s <= ts <= e for s, e in idle_ranges)

        if in_idle:
            noncontributory_count += 1
        elif interaction > config.INTERACTION_THRESH_HIGH:
            direct_count += 1
        elif motion > config.MOTION_THRESH_LOW:
            contributory_count += 1
        else:
            noncontributory_count += 1

    total = direct_count + contributory_count + noncontributory_count
    if total == 0:
        return {"score": 0, "direct_min": 0, "contributory_min": 0,
                "noncontributory_min": 0, "total_min": 0, "deductions": []}

    # Estimate minutes based on sampling interval
    sample_interval_min = config.SAMPLE_EVERY_SEC / 60.0
    direct_min = direct_count * sample_interval_min
    contributory_min = contributory_count * sample_interval_min
    noncontributory_min = noncontributory_count * sample_interval_min
    total_min = total * sample_interval_min

    score = 100 * (direct_min + 0.5 * contributory_min) / max(total_min, 0.01)

    # Penalties for long idles
    deductions = []
    long_idles = [e for e in idle_events
                  if (e.get("end_time_sec", 0) - e.get("start_time_sec", 0)) > config.T_LONG_IDLE_SEC]

    for i, event in enumerate(long_idles):
        if i == 0:
            continue  # skip first
        score -= 5
        deductions.append({
            "event_id": event["event_id"],
            "reason": "Long idle period",
            "penalty": -5,
        })

    score = max(0, min(100, score))

    return {
        "score": round(score, 1),
        "direct_min": round(direct_min, 1),
        "contributory_min": round(contributory_min, 1),
        "noncontributory_min": round(noncontributory_min, 1),
        "total_min": round(total_min, 1),
        "deductions": deductions,
    }


def compute_quality_index(events: List[dict]) -> dict:
    """
    Quality Index (starts at 100):
    + 5 per verification_moment, capped at +20 total
    - 10 per rework_proxy event
    + 5 if Gemini confirms sequence, capped at +10 (handled in pipeline)
    """
    score = 100
    deductions = []

    # Verification moments
    verify_events = [e for e in events if e["type"] == "verification_moment"]
    verify_bonus = min(len(verify_events) * 5, 20)
    score += verify_bonus
    if verify_bonus > 0:
        deductions.append({
            "event_id": verify_events[0]["event_id"] if verify_events else "verify",
            "reason": f"{len(verify_events)} verification moments detected",
            "penalty": verify_bonus,
        })

    # Rework penalties
    rework_events = [e for e in events if e["type"] == "rework_proxy"]
    for event in rework_events:
        score -= 10
        deductions.append({
            "event_id": event["event_id"],
            "reason": "Rework proxy detected",
            "penalty": -10,
        })

    score = max(0, score)

    return {
        "score": score,
        "deductions": deductions,
        "verification_count": len(verify_events),
        "rework_count": len(rework_events),
    }
