"""
render_report.py — Assembles report.md and report_baseline.md from sidecar data.
Works in both rules_only mode (no Gemini) and augmented mode (with Gemini narratives).
"""
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict

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
    narratives=None → rules_only mode (fully rule-based sections).
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    video_names = ", ".join(v.get("filename", "unknown") for v in video_infos)
    sections = []

    # ── Header ──────────────────────────────────────────────────────────────
    sections.append(f"# DAILY SITE REPORT — {run_date} — {video_names}\n")

    # ── Front Page ──────────────────────────────────────────────────────────
    sections.append("## FRONT PAGE\n")

    sections.append("### Top Headlines\n")
    if narratives and "headlines" in narratives:
        sections.append(narratives["headlines"])
    else:
        sections.append(_rule_based_headlines(events, metrics, all_keyframes))
    sections.append("")

    sections.append("### Scoreboard\n")
    sections.append("| Safety | Ergonomics | Productivity | Quality |")
    sections.append("|--------|------------|--------------|---------|")
    sections.append(
        f"| {metrics.get('safety', {}).get('score', 'N/A')}/100 "
        f"| {metrics.get('ergonomics', {}).get('score', 'N/A')}/100 "
        f"| {metrics.get('productivity', {}).get('score', 'N/A')}/100 "
        f"| {metrics.get('quality', {}).get('score', 'N/A')}/100 |"
    )
    sections.append("")

    sections.append("### Must-Watch Clip Reel\n")
    clip_events = _get_clip_reel_events(events)
    if clip_events:
        for event in clip_events:
            clip_path = event.get("evidence", {}).get("clip_path", "")
            eid = event["event_id"]
            ts = event.get("start_time_fmt", "00:00:00")
            etype = event["type"].replace("_", " ").title()
            severity = event.get("severity", "")
            label = event.get("contributing_signals", {}).get("primary_activity", "")
            description = f"{etype} ({severity})"
            if label and label not in ("active", "other"):
                description += f" — {label.replace('_', ' ')}"
            if clip_path:
                sections.append(f"- [{eid} @ {ts}] — {description} — [clip]({clip_path})")
            else:
                sections.append(f"- [{eid} @ {ts}] — {description}")
    else:
        sections.append("*No significant events detected for clip reel.*")
    sections.append("")

    # ── Safety Desk ──────────────────────────────────────────────────────────
    sections.append("## SAFETY DESK\n")
    if narratives and "safety" in narratives:
        sections.append(narratives["safety"])
    else:
        sections.append(_rule_based_safety(events, metrics))
    sections.append("")

    # ── Ergonomics ───────────────────────────────────────────────────────────
    sections.append("## ERGONOMICS\n")
    if narratives and "ergonomics" in narratives:
        sections.append(narratives["ergonomics"])
    else:
        sections.append(_rule_based_ergonomics(events, metrics))
    sections.append("")

    # ── Productivity & Flow ──────────────────────────────────────────────────
    sections.append("## PRODUCTIVITY & FLOW\n")
    if narratives and "productivity" in narratives:
        sections.append(narratives["productivity"])
    else:
        sections.append(_rule_based_productivity(events, metrics))

    # Activity timeline always appended (structured table, complements prose)
    timeline = _build_activity_timeline(all_keyframes)
    if timeline:
        sections.append(timeline)
    sections.append("")

    # ── Quality & Progress ───────────────────────────────────────────────────
    sections.append("## QUALITY & PROGRESS\n")
    if narratives and "quality" in narratives:
        sections.append(narratives["quality"])
    else:
        sections.append(_rule_based_quality(events, metrics))
    sections.append("")

    # ── Per-Video Breakdown ──────────────────────────────────────────────────
    sections.append("## PER-VIDEO BREAKDOWN\n")
    for vinfo in video_infos:
        vname = vinfo.get("filename", "unknown")
        sections.append(f"### {vname}\n")
        sections.append(f"- Duration: {format_timestamp(vinfo.get('duration_sec', 0))}")
        sections.append(f"- Resolution: {vinfo.get('width', '?')}x{vinfo.get('height', '?')}")

        v_events = [e for e in events if e.get("video_file") == vname]
        # Show type distribution
        from collections import Counter
        type_counts = Counter(e["type"] for e in v_events)
        sections.append(f"- Events detected: {len(v_events)}")
        for etype, cnt in type_counts.most_common():
            sections.append(f"  - {etype.replace('_', ' ').title()}: {cnt}")

        # Top 5 by severity
        top5 = sorted(
            v_events,
            key=lambda e: ({"high": 0, "med": 1, "low": 2}.get(e.get("severity", "low"), 2)),
        )[:5]
        for e in top5:
            sections.append(
                f"  - [{e['event_id']} @ {e['start_time_fmt']}] "
                f"{e['type'].replace('_', ' ').title()} ({e['severity']})"
            )
        sections.append("")

    # ── Audit Trail ──────────────────────────────────────────────────────────
    sections.append("## AUDIT TRAIL\n")

    sections.append("### Frames Analyzed\n")
    sections.append("| Frame ID | Video File | Timestamp | Reason | Activity Label |")
    sections.append("|----------|------------|-----------|--------|----------------|")
    for kf in all_keyframes[:100]:
        label_str = ""
        gl = kf.get("gemini_label")
        if gl:
            label_str = gl.get("activity", "")
            if gl.get("interpolated"):
                label_str += " (interp)"
        sections.append(
            f"| {kf.get('frame_id', '')} | {kf.get('video_file', '')} "
            f"| {kf.get('timestamp_fmt', '')} | {kf.get('reason', '')} | {label_str} |"
        )
    if len(all_keyframes) > 100:
        sections.append(f"| ... | ... | ... | ... | ({len(all_keyframes) - 100} more frames) |")
    sections.append("")

    sections.append("### Evidence Index\n")
    sections.append("| Claim | Event ID | Timestamp | Confidence |")
    sections.append("|-------|----------|-----------|------------|")
    for event in events:
        etype = event["type"].replace("_", " ").title()
        conf = event.get("confidence", 0)
        sections.append(
            f"| {etype} ({event['severity']}) | {event['event_id']} "
            f"| {event['start_time_fmt']} | {conf:.2f} |"
        )
    sections.append("")

    report_text = "\n".join(sections)
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
    sections.append(
        "> **Note:** This report was generated using naive uniform frame sampling "
        "without spatial augmentation, depth analysis, or structured event detection. "
        "Compare with `report.md` for the augmented version.\n"
    )
    sections.append(merged_narrative)
    sections.append("")

    sections.append("### Clip Reel (Uniform Sampling)\n")
    for i, sf in enumerate(sample_frames[:12]):
        clip_name = f"baseline_clip_{i}.mp4"
        clip_rel = f"clips/{clip_name}"
        ts = sf.get("timestamp_fmt", "00:00:00")
        vf = sf.get("video_file", "unknown")
        sections.append(f"- [{ts}] — {vf} — [clip]({clip_rel})")
    sections.append("")

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


# ---------------------------------------------------------------------------
# Clip reel selection
# ---------------------------------------------------------------------------

def _get_clip_reel_events(events: List[dict], max_clips: int = 12) -> List[dict]:
    """
    Select up to max_clips events for the clip reel with type diversity.
    Priority order: ppe_violation > near_miss > occlusion > hazard >
                    sustained_work > rework > verification > transition > idle
    Max 2 clips per event type to ensure variety.
    """
    TYPE_PRIORITY = {
        "ppe_violation":        0,
        "near_miss_proxy":      1,
        "occlusion_critical":   2,
        "approach_hazard_proxy": 3,
        "sustained_work":       4,
        "rework_proxy":         5,
        "verification_moment":  6,
        "task_transition":      7,
        "idle_streak":          8,
    }
    SEV_PRIORITY = {"high": 0, "med": 1, "low": 2}
    MAX_PER_TYPE = 2

    sorted_events = sorted(
        events,
        key=lambda e: (
            SEV_PRIORITY.get(e.get("severity", "low"), 2),
            TYPE_PRIORITY.get(e.get("type", ""), 99),
        ),
    )

    selected = []
    type_counts: Dict[str, int] = {}

    for event in sorted_events:
        etype = event.get("type", "")
        if type_counts.get(etype, 0) < MAX_PER_TYPE:
            selected.append(event)
            type_counts[etype] = type_counts.get(etype, 0) + 1
        if len(selected) >= max_clips:
            break

    return selected


# ---------------------------------------------------------------------------
# Activity timeline (from Gemini labels)
# ---------------------------------------------------------------------------

def _build_activity_timeline(all_keyframes: List[dict]) -> str:
    """
    Build an activity timeline table from Gemini-labeled keyframes.
    Groups consecutive frames with the same activity into segments.
    Returns an empty string if no labeled frames exist.
    """
    labeled = [
        kf for kf in all_keyframes
        if kf.get("gemini_label")
        and not kf["gemini_label"].get("interpolated")
        and kf["gemini_label"].get("confidence", 0) >= config.ACTIVITY_LABEL_CONF_THRESH
    ]
    if not labeled:
        return ""

    # Group by video
    by_video: Dict[str, List[dict]] = {}
    for kf in labeled:
        by_video.setdefault(kf.get("video_file", "unknown"), []).append(kf)

    lines = ["\n**Activity Timeline (Gemini-labeled):**\n"]
    lines.append("| Video | Time Range | Activity | Tool | Duration |")
    lines.append("|-------|------------|----------|------|----------|")

    any_row = False
    for vid, kfs in by_video.items():
        kfs.sort(key=lambda x: x["timestamp_sec"])

        segments = []
        cur_activity = None
        cur_tool = None
        cur_start = None
        cur_end = None

        for kf in kfs:
            gl = kf["gemini_label"]
            activity = gl.get("activity", "other")
            tool = gl.get("tool_held", "unknown")

            if activity != cur_activity:
                if cur_activity is not None:
                    segments.append((cur_start, cur_end, cur_activity, cur_tool))
                cur_activity = activity
                cur_tool = tool
                cur_start = kf["timestamp_sec"]
                cur_end = kf["timestamp_sec"]
            else:
                cur_end = kf["timestamp_sec"]

        if cur_activity is not None:
            segments.append((cur_start, cur_end, cur_activity, cur_tool))

        for start, end, activity, tool in segments:
            dur_min = (end - start) / 60.0
            if dur_min < 0.2:
                continue
            s_fmt = format_timestamp(start)
            e_fmt = format_timestamp(end)
            act_str = activity.replace("_", " ").title()
            tool_str = tool if tool not in ("none", "unknown") else "—"
            lines.append(
                f"| {vid} | {s_fmt}–{e_fmt} | {act_str} | {tool_str} | {dur_min:.1f} min |"
            )
            any_row = True

    return "\n".join(lines) if any_row else ""


# ---------------------------------------------------------------------------
# Rule-based section builders
# ---------------------------------------------------------------------------

def _rule_based_headlines(
    events: List[dict], metrics: dict, all_keyframes: List[dict] = None
) -> str:
    """Generate rule-based headlines without Gemini."""
    lines = []
    safety_score = metrics.get("safety", {}).get("score", "N/A")
    prod_score = metrics.get("productivity", {}).get("score", "N/A")
    quality_score = metrics.get("quality", {}).get("score", "N/A")

    # PPE violations first (always front-page)
    ppe_events = [e for e in events if e.get("type") == "ppe_violation"]
    if ppe_events:
        total_sec = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in ppe_events
        )
        lines.append(
            f"- **PPE ALERT:** Protective gloves not worn for {total_sec/60:.1f} min "
            f"across {len(ppe_events)} period(s) during active work "
            f"[{ppe_events[0]['event_id']} @ {ppe_events[0]['start_time_fmt']}]"
        )

    # Other high-severity safety events
    high_events = [
        e for e in events
        if e.get("severity") == "high" and e.get("type") != "ppe_violation"
    ]
    for e in high_events[:2]:
        lines.append(
            f"- **{e['type'].replace('_', ' ').title()}** detected "
            f"[{e['event_id']} @ {e['start_time_fmt']}]"
        )

    # Primary activity from productivity breakdown
    prod = metrics.get("productivity", {})
    breakdown = prod.get("activity_breakdown", {})
    if breakdown:
        top = max(breakdown.items(), key=lambda x: x[1], default=None)
        if top and top[0] not in ("idle", "motion"):
            lines.append(
                f"- Primary activity: **{top[0].replace('_', ' ').title()}** "
                f"— {top[1]:.0f} min"
            )

    # Sustained work
    sustained = [e for e in events if e.get("type") == "sustained_work"]
    if sustained:
        total_work = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in sustained
        )
        lines.append(
            f"- {len(sustained)} sustained work period(s) totaling "
            f"{total_work/60:.0f} min"
        )

    lines.append(
        f"- Safety: **{safety_score}/100** | "
        f"Productivity: **{prod_score}/100** | "
        f"Quality: **{quality_score}/100**"
    )

    idle_events = [e for e in events if e.get("type") == "idle_streak"]
    if idle_events:
        total_idle = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in idle_events
        )
        lines.append(
            f"- Total idle: {total_idle/60:.1f} min across {len(idle_events)} period(s)"
        )

    return "\n".join(lines)


def _rule_based_safety(events: List[dict], metrics: dict) -> str:
    """Generate rule-based safety section."""
    safety = metrics.get("safety", {})
    lines = [f"**Safety Score: {safety.get('score', 'N/A')}/100**\n"]

    # PPE section
    ppe_events = [e for e in events if e["type"] == "ppe_violation"]
    if ppe_events:
        lines.append("### PPE Compliance\n")
        total_sec = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in ppe_events
        )
        lines.append(
            f"**Protective gloves not worn** for {total_sec/60:.1f} min "
            f"across {len(ppe_events)} active-work period(s)."
        )
        for e in ppe_events[:3]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            lines.append(
                f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                f"{dur:.0f}s without protective gloves (confidence: {e['confidence']:.2f})"
            )
        lines.append("")
    else:
        lines.append("### PPE Compliance\n")
        lines.append("No glove violations detected during active work periods.\n")

    # Standard OSHA categories
    safety_events = [
        e for e in events
        if e["type"] in ("near_miss_proxy", "occlusion_critical", "approach_hazard_proxy")
    ]

    categories = {
        "Falls": [],
        "Struck-By": [],
        "Caught-In/Between": [],
        "Electrical": [],
    }
    for e in safety_events:
        if e["type"] == "approach_hazard_proxy":
            categories["Falls"].append(e)
        elif e["type"] == "near_miss_proxy":
            categories["Struck-By"].append(e)
        elif e["type"] == "occlusion_critical":
            categories["Caught-In/Between"].append(e)

    for cat_name, cat_events in categories.items():
        lines.append(f"### {cat_name}\n")
        if not cat_events:
            lines.append("No events detected in this category.\n")
            continue
        total_dur = sum(
            e.get("end_time_sec", 0) - e.get("start_time_sec", 0) for e in cat_events
        )
        lines.append(f"- Exposure: {total_dur/60:.1f} min")
        lines.append(f"- Event count: {len(cat_events)}")
        for e in cat_events[:3]:
            lines.append(
                f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                f"{e['type'].replace('_', ' ')} "
                f"(severity: {e['severity']}, confidence: {e['confidence']:.2f})"
            )
        lines.append("")

    return "\n".join(lines)


def _rule_based_ergonomics(events: List[dict], metrics: dict) -> str:
    """Generate rule-based ergonomics section."""
    ergo = metrics.get("ergonomics", {})
    rework_events = [e for e in events if e["type"] == "rework_proxy"]

    lines = [f"**Ergonomics Score: {ergo.get('score', 'N/A')}/100**\n"]
    lines.append(f"- High-motion manipulation segments: {ergo.get('high_motion_segments', 0)}")

    if rework_events:
        lines.append(f"- Repetitive motion clusters: {len(rework_events)}")
        for e in rework_events[:3]:
            region = e.get("contributing_signals", {}).get("spatial_region", "?")
            lines.append(
                f"  - [{e['event_id']} @ {e['start_time_fmt']}] — Region {region}"
            )

    if ergo.get("deductions"):
        lines.append("\n**Recommended interventions:**")
        lines.append("- Schedule micro-breaks during sustained high-motion periods")
        lines.append("- Rotate tasks to reduce repetitive strain risk")

    return "\n".join(lines)


def _rule_based_productivity(events: List[dict], metrics: dict) -> str:
    """Generate rule-based productivity section."""
    prod = metrics.get("productivity", {})
    lines = [f"**Productivity Score: {prod.get('score', 'N/A')}/100**\n"]

    total = prod.get("total_min", 0)
    if total > 0:
        direct_pct = (prod.get("direct_min", 0) / total) * 100
        contrib_pct = (prod.get("contributory_min", 0) / total) * 100
        noncontrib_pct = (prod.get("noncontributory_min", 0) / total) * 100
    else:
        direct_pct = contrib_pct = noncontrib_pct = 0

    lines.append("| Category | Minutes | % |")
    lines.append("|----------|---------|---|")
    lines.append(f"| Direct Work | {prod.get('direct_min', 0):.1f} | {direct_pct:.1f}% |")
    lines.append(f"| Contributory | {prod.get('contributory_min', 0):.1f} | {contrib_pct:.1f}% |")
    lines.append(f"| Noncontributory | {prod.get('noncontributory_min', 0):.1f} | {noncontrib_pct:.1f}% |")
    lines.append(f"| **Total** | **{total:.1f}** | **100%** |")
    lines.append("")

    label_cov = prod.get("label_coverage_pct", 0)
    if label_cov > 0:
        lines.append(f"*Classification uses Gemini labels ({label_cov:.0f}% of frames labeled) "
                     f"with signal-based fallback.*\n")

    # Activity breakdown (from Gemini labels)
    breakdown = prod.get("activity_breakdown", {})
    if breakdown:
        lines.append("**Activity Breakdown:**\n")
        lines.append("| Activity | Minutes |")
        lines.append("|----------|---------|")
        for activity, mins in sorted(breakdown.items(), key=lambda x: -x[1]):
            if mins < 0.1:
                continue
            act_str = activity.replace("_", " ").title()
            lines.append(f"| {act_str} | {mins:.1f} |")
        lines.append("")

    # Biggest blockers
    idle_events = sorted(
        [e for e in events if e["type"] == "idle_streak"],
        key=lambda e: e.get("contributing_signals", {}).get("duration_sec", 0),
        reverse=True,
    )
    if idle_events:
        lines.append("**Idle Periods:**")
        for e in idle_events[:3]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            lines.append(
                f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                f"Idle for {dur:.0f}s ({e['severity']})"
            )
        lines.append("")

    # Sustained work summary
    sustained = [e for e in events if e.get("type") == "sustained_work"]
    if sustained:
        lines.append("**Sustained Work Periods:**")
        for e in sustained[:5]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            act = e.get("contributing_signals", {}).get("primary_activity", "active")
            lines.append(
                f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                f"{act.replace('_', ' ').title()} for {dur/60:.1f} min ({e['severity']})"
            )
        lines.append("")

    return "\n".join(lines)


def _rule_based_quality(events: List[dict], metrics: dict) -> str:
    """Generate rule-based quality section."""
    qual = metrics.get("quality", {})
    verify_events = [e for e in events if e["type"] == "verification_moment"]
    rework_events = [e for e in events if e["type"] == "rework_proxy"]
    sustained_events = [e for e in events if e["type"] == "sustained_work"]

    lines = [f"**Quality Score: {qual.get('score', 'N/A')}/100**\n"]

    if sustained_events:
        lines.append(f"**Sustained Work Periods ({len(sustained_events)}):**")
        for e in sustained_events[:5]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            act = e.get("contributing_signals", {}).get("primary_activity", "active")
            lines.append(
                f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                f"{act.replace('_', ' ').title()} for {dur/60:.1f} min"
            )
        lines.append("")

    if verify_events:
        lines.append(f"**Verification Moments ({len(verify_events)}):**")
        for e in verify_events[:5]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            trigger = e.get("contributing_signals", {}).get("trigger", "signal")
            lines.append(
                f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                f"Quality check ({dur:.1f}s, via {trigger})"
            )
        lines.append("")

    if rework_events:
        lines.append(f"**Rework Signals ({len(rework_events)}):**")
        for e in rework_events[:3]:
            region = e.get("contributing_signals", {}).get("spatial_region", "?")
            lines.append(
                f"- [{e['event_id']} @ {e['start_time_fmt']}] — "
                f"Repeated activity in region {region}"
            )
        lines.append("")

    if not any([sustained_events, verify_events, rework_events]):
        lines.append("*No quality signals detected. Run in augmented mode for deeper analysis.*")

    return "\n".join(lines)
