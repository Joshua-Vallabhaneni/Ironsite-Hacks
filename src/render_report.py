"""
render_report.py — Assembles report.md and report_baseline.md from sidecar data.
Works in both rules_only mode (no Gemini) and augmented mode (with Gemini narratives).
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Optional

from . import config
from .video_io import format_timestamp

log = logging.getLogger(__name__)


def render_augmented_report(
    events: List[dict],
    metrics: dict,
    all_keyframes: List[dict],
    video_infos: List[dict],
    output_dir: str,
    narratives: dict = None,
    run_date: str = None,
) -> str:
    """
    Render the full augmented report.md.
    If narratives is None, uses rule-based report (rules_only mode).
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    video_names = ", ".join(v.get("filename", "unknown") for v in video_infos)

    sections = []

    # --- Header ---
    sections.append(f"# DAILY SITE REPORT — {run_date} — {video_names}\n")

    # --- Front Page ---
    sections.append("## FRONT PAGE\n")

    # Headlines
    sections.append("### Top Headlines\n")
    if narratives and "headlines" in narratives:
        sections.append(narratives["headlines"])
    else:
        sections.append(_rule_based_headlines(events, metrics))
    sections.append("")

    # Scoreboard
    sections.append("### Scoreboard\n")
    sections.append("| Safety | Ergonomics | Productivity | Quality |")
    sections.append("|--------|------------|--------------|---------|")
    sections.append(f"| {metrics.get('safety', {}).get('score', 'N/A')}/100 "
                    f"| {metrics.get('ergonomics', {}).get('score', 'N/A')}/100 "
                    f"| {metrics.get('productivity', {}).get('score', 'N/A')}/100 "
                    f"| {metrics.get('quality', {}).get('score', 'N/A')}/100 |")
    sections.append("")

    # Must-Watch Clip Reel
    sections.append("### Must-Watch Clip Reel\n")
    clip_events = _get_clip_reel_events(events)
    for event in clip_events:
        clip_path = event.get("evidence", {}).get("clip_path", "")
        eid = event["event_id"]
        ts = event.get("start_time_fmt", "00:00:00")
        etype = event["type"].replace("_", " ").title()
        severity = event.get("severity", "")
        if clip_path:
            sections.append(f"- [{eid} @ {ts}] — {etype} ({severity}) — [clip]({clip_path})")
        else:
            sections.append(f"- [{eid} @ {ts}] — {etype} ({severity})")
    sections.append("")

    # --- Safety Desk ---
    sections.append("## SAFETY DESK\n")
    if narratives and "safety" in narratives:
        sections.append(narratives["safety"])
    else:
        sections.append(_rule_based_safety(events, metrics))
    sections.append("")

    # --- Ergonomics ---
    sections.append("## ERGONOMICS\n")
    if narratives and "ergonomics" in narratives:
        sections.append(narratives["ergonomics"])
    else:
        sections.append(_rule_based_ergonomics(events, metrics))
    sections.append("")

    # --- Productivity & Flow ---
    sections.append("## PRODUCTIVITY & FLOW\n")
    if narratives and "productivity" in narratives:
        sections.append(narratives["productivity"])
    else:
        sections.append(_rule_based_productivity(events, metrics))
    sections.append("")

    # --- Quality & Progress ---
    sections.append("## QUALITY & PROGRESS\n")
    if narratives and "quality" in narratives:
        sections.append(narratives["quality"])
    else:
        sections.append(_rule_based_quality(events, metrics))
    sections.append("")

    # --- Per-Video Sections ---
    sections.append("## PER-VIDEO BREAKDOWN\n")
    for vinfo in video_infos:
        vname = vinfo.get("filename", "unknown")
        sections.append(f"### {vname}\n")
        sections.append(f"- Duration: {format_timestamp(vinfo.get('duration_sec', 0))}")
        sections.append(f"- Resolution: {vinfo.get('width', '?')}x{vinfo.get('height', '?')}")

        v_events = [e for e in events if e.get("video_file") == vname]
        sections.append(f"- Events detected: {len(v_events)}")

        for e in v_events[:5]:
            sections.append(f"  - [{e['event_id']} @ {e['start_time_fmt']}] "
                          f"{e['type'].replace('_', ' ').title()} ({e['severity']})")
        sections.append("")

    # --- Audit Trail ---
    sections.append("## AUDIT TRAIL\n")

    # Frames Analyzed
    sections.append("### Frames Analyzed\n")
    sections.append("| Frame ID | Video File | Timestamp | Selection Reason |")
    sections.append("|----------|------------|-----------|-----------------|")
    for kf in all_keyframes[:100]:  # Cap at 100 rows
        sections.append(f"| {kf.get('frame_id', '')} | {kf.get('video_file', '')} "
                       f"| {kf.get('timestamp_fmt', '')} | {kf.get('reason', '')} |")
    if len(all_keyframes) > 100:
        sections.append(f"| ... | ... | ... | ({len(all_keyframes) - 100} more frames) |")
    sections.append("")

    # Evidence Index
    sections.append("### Evidence Index\n")
    sections.append("| Claim | Event ID | Timestamp |")
    sections.append("|-------|----------|-----------|")
    for event in events:
        etype = event["type"].replace("_", " ").title()
        sections.append(f"| {etype} ({event['severity']}) | {event['event_id']} "
                       f"| {event['start_time_fmt']} |")
    sections.append("")

    report_text = "\n".join(sections)

    # Save report
    report_path = os.path.join(output_dir, "report.md")
    with open(report_path, "w") as f:
        f.write(report_text)
    log.info(f"Report saved to {report_path}")

    return report_path


def render_baseline_report(
    merged_narrative: str,
    sample_frames: List[dict],
    video_infos: List[dict],
    output_dir: str,
    run_date: str = None,
) -> str:
    """Render the baseline comparison report."""
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    video_names = ", ".join(v.get("filename", "unknown") for v in video_infos)

    sections = []
    sections.append(f"# DAILY SITE REPORT (BASELINE) — {run_date} — {video_names}\n")
    sections.append("> **Note:** This report was generated using naive uniform frame sampling "
                    "without spatial augmentation, depth analysis, or structured event detection. "
                    "Compare with `report.md` for the augmented version.\n")

    sections.append(merged_narrative)
    sections.append("")

    # Clip reel from uniform samples
    sections.append("### Clip Reel (Uniform Sampling)\n")
    clips_dir = os.path.join(output_dir, "clips")
    for i, sf in enumerate(sample_frames[:12]):
        clip_name = f"baseline_clip_{i}.mp4"
        clip_rel = f"clips/{clip_name}"
        ts = sf.get("timestamp_fmt", "00:00:00")
        vf = sf.get("video_file", "unknown")
        sections.append(f"- [{ts}] — {vf} — [clip]({clip_rel})")
    sections.append("")

    # Audit trail
    sections.append("## AUDIT TRAIL\n")
    sections.append(f"- Total frames sampled: {len(sample_frames)}")
    sections.append(f"- Videos analyzed: {len(video_infos)}")
    sections.append(f"- Method: Uniform sampling, {config.BASELINE_MAX_FRAMES} frames max")
    sections.append("")

    report_text = "\n".join(sections)

    report_path = os.path.join(output_dir, "report_baseline.md")
    with open(report_path, "w") as f:
        f.write(report_text)
    log.info(f"Baseline report saved to {report_path}")

    return report_path


def _get_clip_reel_events(events: List[dict], max_clips: int = 12) -> List[dict]:
    """Select 5-12 most important events for the clip reel."""
    # Sort by severity, then by type importance
    type_priority = {
        "near_miss_proxy": 0,
        "occlusion_critical": 1,
        "approach_hazard_proxy": 2,
        "rework_proxy": 3,
        "task_transition": 4,
        "verification_moment": 5,
        "idle_streak": 6,
    }
    severity_priority = {"high": 0, "med": 1, "low": 2}

    sorted_events = sorted(events, key=lambda e: (
        severity_priority.get(e.get("severity", "low"), 2),
        type_priority.get(e.get("type", ""), 99),
    ))

    # Take up to max_clips, but at least 5 if available
    return sorted_events[:max(5, min(max_clips, len(sorted_events)))]


def _rule_based_headlines(events: List[dict], metrics: dict) -> str:
    """Generate rule-based headlines without Gemini."""
    lines = []

    safety_score = metrics.get("safety", {}).get("score", "N/A")
    prod_score = metrics.get("productivity", {}).get("score", "N/A")
    quality_score = metrics.get("quality", {}).get("score", "N/A")

    # High severity events
    high_events = [e for e in events if e.get("severity") == "high"]
    for e in high_events[:2]:
        lines.append(f"- ⚠️ **{e['type'].replace('_', ' ').title()}** detected — "
                     f"[{e['event_id']} @ {e['start_time_fmt']}]")

    lines.append(f"- Safety Index: **{safety_score}/100** — "
                 f"{metrics.get('safety', {}).get('event_count', 0)} safety events detected")
    lines.append(f"- Productivity Index: **{prod_score}/100** — "
                 f"{metrics.get('productivity', {}).get('direct_min', 0):.0f} min direct work")
    lines.append(f"- Quality Score: **{quality_score}/100** — "
                 f"{metrics.get('quality', {}).get('verification_count', 0)} verification moments")

    idle_events = [e for e in events if e.get("type") == "idle_streak"]
    if idle_events:
        total_idle = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in idle_events
        )
        lines.append(f"- Total idle time: {total_idle/60:.1f} minutes across {len(idle_events)} periods")

    return "\n".join(lines)


def _rule_based_safety(events: List[dict], metrics: dict) -> str:
    """Generate rule-based safety section."""
    safety_events = [e for e in events
                     if e["type"] in ("near_miss_proxy", "occlusion_critical", "approach_hazard_proxy")]

    lines = []
    lines.append(f"**Safety Score: {metrics.get('safety', {}).get('score', 'N/A')}/100**\n")

    categories = {
        "Falls": [],
        "Struck-By": [],
        "Caught-In/Between": [],
        "Electrical": [],
    }

    # Map events to categories (best-effort)
    for e in safety_events:
        if e["type"] == "near_miss_proxy":
            categories["Struck-By"].append(e)
        elif e["type"] == "occlusion_critical":
            categories["Caught-In/Between"].append(e)
        elif e["type"] == "approach_hazard_proxy":
            categories["Falls"].append(e)

    for cat_name, cat_events in categories.items():
        lines.append(f"### {cat_name}")
        if not cat_events:
            lines.append("No events detected in this category.\n")
            continue

        total_duration = sum(e.get("end_time_sec", 0) - e.get("start_time_sec", 0) for e in cat_events)
        lines.append(f"- Exposure: {total_duration/60:.1f} minutes")
        lines.append(f"- Event count: {len(cat_events)}")

        for e in cat_events[:3]:
            lines.append(f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                        f"{e['type'].replace('_', ' ')} (severity: {e['severity']}, "
                        f"confidence: {e['confidence']:.2f})")
        lines.append("")

    return "\n".join(lines)


def _rule_based_ergonomics(events: List[dict], metrics: dict) -> str:
    """Generate rule-based ergonomics section."""
    ergo = metrics.get("ergonomics", {})
    rework_events = [e for e in events if e["type"] == "rework_proxy"]

    lines = []
    lines.append(f"**Ergonomics Score: {ergo.get('score', 'N/A')}/100**\n")
    lines.append(f"- High-motion segments: {ergo.get('high_motion_segments', 0)}")

    if rework_events:
        lines.append(f"- Repetitive motion clusters: {len(rework_events)}")
        for e in rework_events[:3]:
            lines.append(f"  - [{e['event_id']} @ {e['start_time_fmt']}] — "
                        f"Region {e.get('contributing_signals', {}).get('spatial_region', '?')}")

    if ergo.get("deductions"):
        lines.append("\n**Recommended interventions:**")
        lines.append("- Schedule micro-breaks during sustained high-motion periods")
        lines.append("- Rotate tasks to reduce repetitive strain risk")

    return "\n".join(lines)


def _rule_based_productivity(events: List[dict], metrics: dict) -> str:
    """Generate rule-based productivity section."""
    prod = metrics.get("productivity", {})

    lines = []
    lines.append(f"**Productivity Score: {prod.get('score', 'N/A')}/100**\n")

    total = prod.get("total_min", 0)
    if total > 0:
        direct_pct = (prod.get("direct_min", 0) / total) * 100
        contrib_pct = (prod.get("contributory_min", 0) / total) * 100
        noncontrib_pct = (prod.get("noncontributory_min", 0) / total) * 100
    else:
        direct_pct = contrib_pct = noncontrib_pct = 0

    lines.append(f"| Category | Minutes | Percentage |")
    lines.append(f"|----------|---------|------------|")
    lines.append(f"| Direct Work | {prod.get('direct_min', 0):.1f} | {direct_pct:.1f}% |")
    lines.append(f"| Contributory | {prod.get('contributory_min', 0):.1f} | {contrib_pct:.1f}% |")
    lines.append(f"| Noncontributory | {prod.get('noncontributory_min', 0):.1f} | {noncontrib_pct:.1f}% |")
    lines.append(f"| **Total** | **{total:.1f}** | **100%** |")
    lines.append("")

    # Biggest blockers
    idle_events = sorted(
        [e for e in events if e["type"] == "idle_streak"],
        key=lambda e: e.get("contributing_signals", {}).get("duration_sec", 0),
        reverse=True,
    )
    if idle_events:
        lines.append("**Biggest blockers:**")
        for e in idle_events[:3]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            lines.append(f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                        f"Idle for {dur:.0f}s ({e['severity']})")
    lines.append("")

    return "\n".join(lines)


def _rule_based_quality(events: List[dict], metrics: dict) -> str:
    """Generate rule-based quality section."""
    qual = metrics.get("quality", {})
    verify_events = [e for e in events if e["type"] == "verification_moment"]
    rework_events = [e for e in events if e["type"] == "rework_proxy"]

    lines = []
    lines.append(f"**Quality Score: {qual.get('score', 'N/A')}/100**\n")

    if verify_events:
        lines.append(f"**Verification Moments ({len(verify_events)}):**")
        for e in verify_events[:5]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            lines.append(f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                        f"Quality check ({dur:.1f}s)")

    if rework_events:
        lines.append(f"\n**Rework Signals ({len(rework_events)}):**")
        for e in rework_events[:3]:
            region = e.get("contributing_signals", {}).get("spatial_region", "?")
            lines.append(f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                        f"Repeated activity in region {region}")

    return "\n".join(lines)
