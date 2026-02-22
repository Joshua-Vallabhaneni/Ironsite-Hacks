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
    ergo_score = metrics.get("ergonomics", {}).get("score", "N/A")

    # Score summary
    lines.append(
        f"- Today's site performance scores: Safety **{safety_score}/100**, "
        f"Productivity **{prod_score}/100**, Ergonomics **{ergo_score}/100**, "
        f"Quality **{quality_score}/100**."
    )

    # PPE violations
    ppe_events = [e for e in events if e.get("type") == "ppe_violation"]
    if ppe_events:
        total_sec = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in ppe_events
        )
        lines.append(
            f"- **PPE Alert:** Protective gloves were not observed during active masonry work "
            f"for a combined total of {total_sec/60:.1f} minutes across {len(ppe_events)} period(s) — "
            f"follow-up required with the worker. "
            f"[{ppe_events[0]['event_id']} @ {ppe_events[0]['start_time_fmt']}]"
        )

    # Sustained work — the positive lead
    sustained = [e for e in events if e.get("type") == "sustained_work"]
    if sustained:
        total_work = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in sustained
        )
        best = max(sustained, key=lambda e: e.get("contributing_signals", {}).get("duration_sec", 0))
        act = best.get("contributing_signals", {}).get("primary_activity", "active work")
        lines.append(
            f"- The worker maintained {len(sustained)} sustained productive period(s) totalling "
            f"{total_work/60:.0f} minutes — the longest uninterrupted run was "
            f"{best.get('contributing_signals', {}).get('duration_sec', 0)/60:.1f} minutes "
            f"of {act.replace('_', ' ')}. "
            f"[{best['event_id']} @ {best['start_time_fmt']}]"
        )
    else:
        # Fallback: show primary activity from breakdown
        prod = metrics.get("productivity", {})
        breakdown = prod.get("activity_breakdown", {})
        if breakdown:
            top = max(breakdown.items(), key=lambda x: x[1], default=None)
            if top and top[0] not in ("idle", "motion"):
                lines.append(
                    f"- The dominant activity this shift was **{top[0].replace('_', ' ').title()}** "
                    f"at approximately {top[1]:.0f} minutes of observed time."
                )

    # Rework signals
    rework_events = [e for e in events if e.get("type") == "rework_proxy"]
    if rework_events:
        lines.append(
            f"- **Quality Flag:** {len(rework_events)} workspace zone(s) showed repeated high-intensity "
            f"activity with return visits after 60+ second gaps — the worker may have needed to adjust "
            f"or redo earlier brickwork in these areas. "
            f"[{rework_events[0]['event_id']} @ {rework_events[0]['start_time_fmt']}]"
        )

    # Near-miss
    near_miss = [e for e in events if e.get("type") == "near_miss_proxy"]
    if near_miss:
        lines.append(
            f"- **Safety Note:** {len(near_miss)} instance(s) of high-risk tool use posture detected — "
            f"worker was using a tool while crouching or reaching overhead, increasing the risk of "
            f"tool slip or loss of balance. "
            f"[{near_miss[0]['event_id']} @ {near_miss[0]['start_time_fmt']}]"
        )

    # Idle periods
    idle_events = [e for e in events if e.get("type") == "idle_streak"]
    if idle_events:
        total_idle = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in idle_events
        )
        lines.append(
            f"- The worker was inactive for approximately {total_idle/60:.1f} minutes "
            f"across {len(idle_events)} period(s), likely due to rest breaks or material waits."
        )

    return "\n".join(lines)


def _rule_based_safety(events: List[dict], metrics: dict) -> str:
    """Generate rule-based safety section."""
    safety = metrics.get("safety", {})
    score = safety.get("score", "N/A")

    ppe_events = [e for e in events if e["type"] == "ppe_violation"]
    near_miss_events = [e for e in events if e["type"] == "near_miss_proxy"]
    hazard_events = [e for e in events if e["type"] == "approach_hazard_proxy"]
    occlusion_events = [e for e in events if e["type"] == "occlusion_critical"]
    total_safety_events = len(ppe_events) + len(near_miss_events) + len(hazard_events) + len(occlusion_events)

    lines = []

    # Opening summary
    if total_safety_events == 0:
        lines.append(
            f"**Safety Score: {score}/100** — No safety events were flagged during this shift. "
            f"The worker operated within normal parameters throughout the recorded footage.\n"
        )
    else:
        lines.append(
            f"**Safety Score: {score}/100** — {total_safety_events} safety-relevant observation(s) "
            f"were recorded during this shift and are detailed below.\n"
        )

    # PPE Compliance
    lines.append("### PPE Compliance\n")
    if ppe_events:
        total_sec = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in ppe_events
        )
        lines.append(
            f"Protective gloves were not observed during active masonry work for approximately "
            f"{total_sec/60:.1f} minutes across {len(ppe_events)} period(s). During these windows "
            f"the worker was engaged in brick laying, mortar application, or material handling — "
            f"activities with direct hand exposure risk. Supervisors should verify whether gloves "
            f"were present but obscured by the camera angle, or whether PPE compliance needs reinforcement.\n"
        )
        for e in ppe_events[:3]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            lines.append(
                f"- At {e['start_time_fmt']}, a {dur:.0f}-second period of active masonry work "
                f"without visible protective gloves was recorded. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")
    else:
        lines.append(
            "No glove violations were detected during active work periods. "
            "The worker appeared to have appropriate hand protection throughout the shift.\n"
        )

    # Tool Handling & Near-Miss
    lines.append("### Tool Handling Risk\n")
    if near_miss_events:
        lines.append(
            f"{len(near_miss_events)} instance(s) were detected where the worker was using a tool "
            f"while in a physically demanding posture — specifically crouching or reaching overhead. "
            f"These positions reduce stability and reaction time, increasing the risk of tool slip, "
            f"dropped equipment, or loss of balance.\n"
        )
        for e in near_miss_events[:3]:
            sigs = e.get("contributing_signals", {})
            posture = sigs.get("posture", "awkward posture").replace("_", " ")
            tool = sigs.get("tool_held", "a tool")
            activity = sigs.get("activity", "active work").replace("_", " ")
            lines.append(
                f"- At {e['start_time_fmt']}, the worker was {activity} with a {tool} "
                f"while in a {posture} position. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")
    else:
        lines.append("No high-risk tool postures were detected during this shift.\n")

    # Fall & Approach Risk
    lines.append("### Fall & Approach Risk\n")
    if hazard_events:
        lines.append(
            f"{len(hazard_events)} instance(s) were detected where the worker's camera showed "
            f"a steady approach toward a surface with increasing depth variation — indicating "
            f"movement toward a ledge, step edge, or uneven ground.\n"
        )
        for e in hazard_events[:3]:
            duration = round(e.get("end_time_sec", 0) - e.get("start_time_sec", 0))
            lines.append(
                f"- At {e['start_time_fmt']}, depth analysis tracked a {duration}-second "
                f"approach sequence toward a surface discontinuity. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")
    else:
        lines.append("No fall hazard or approach risk events were detected.\n")

    # Obstruction
    lines.append("### Obstruction & Confined Space\n")
    if occlusion_events:
        lines.append(
            f"{len(occlusion_events)} period(s) of sustained visual complexity during high-intensity "
            f"work were detected, suggesting the worker may have been operating in a cluttered or "
            f"confined area where visibility of hands and tools was reduced.\n"
        )
        for e in occlusion_events[:2]:
            sigs = e.get("contributing_signals", {})
            frames = sigs.get("consecutive_frames", "?")
            lines.append(
                f"- At {e['start_time_fmt']}, elevated depth complexity persisted across "
                f"{frames} consecutive frames during active work. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")
    else:
        lines.append("No obstruction or confined-space events were detected.\n")

    return "\n".join(lines)


def _rule_based_ergonomics(events: List[dict], metrics: dict) -> str:
    """Generate rule-based ergonomics section."""
    ergo = metrics.get("ergonomics", {})
    score = ergo.get("score", "N/A")
    rework_events = [e for e in events if e["type"] == "rework_proxy"]
    near_miss_events = [e for e in events if e["type"] == "near_miss_proxy"]
    high_motion = ergo.get("high_motion_segments", 0)

    lines = []

    # Opening
    if rework_events or near_miss_events or high_motion > 0:
        lines.append(
            f"**Ergonomics Score: {score}/100** — Ergonomic risk signals were present during this shift. "
            f"Repeated physical effort in the same workspace zones and awkward postures during tool use "
            f"can contribute to cumulative strain injuries if sustained over multiple shifts.\n"
        )
    else:
        lines.append(
            f"**Ergonomics Score: {score}/100** — No significant ergonomic risk events were flagged "
            f"during this shift. Worker movement patterns were within acceptable parameters.\n"
        )

    # Repetitive motion
    lines.append("### Repetitive Motion & Return-to-Zone Activity\n")
    if rework_events:
        total_exposure = sum(
            max(0, e.get("end_time_sec", 0) - e.get("start_time_sec", 0))
            for e in rework_events
        )
        lines.append(
            f"{len(rework_events)} workspace zone(s) showed a pattern of repeated high-intensity "
            f"activity with the worker returning after a gap of 60 seconds or more. This pattern — "
            f"working in an area, stepping away, then returning to the same physical movements — "
            f"accumulates strain on the same muscle groups. Total exposure across these events: "
            f"approximately {total_exposure/60:.1f} minutes.\n"
        )
        for e in rework_events[:3]:
            sigs = e.get("contributing_signals", {})
            region = sigs.get("spatial_region", "?")
            gap = sigs.get("gap_sec", 0)
            lines.append(
                f"- Starting at {e['start_time_fmt']}, the worker returned to workspace zone {region} "
                f"after a {gap:.0f}-second break and resumed high-intensity activity in the same area. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")
    else:
        lines.append(
            "No repeated-zone activity with significant return gaps was detected. "
            "The worker moved through work areas without the return patterns associated with rework.\n"
        )

    # Posture strain
    if near_miss_events:
        lines.append("### Posture & Joint Stress\n")
        lines.append(
            f"{len(near_miss_events)} instance(s) of physically demanding posture during active "
            f"tool use were recorded. Crouching and reaching overhead with tools places significant "
            f"stress on the knees, lower back, and shoulders — particularly during repetitive "
            f"masonry tasks.\n"
        )
        for e in near_miss_events[:3]:
            sigs = e.get("contributing_signals", {})
            posture = sigs.get("posture", "demanding posture").replace("_", " ")
            activity = sigs.get("activity", "active work").replace("_", " ")
            lines.append(
                f"- At {e['start_time_fmt']}, the worker was {activity} in a {posture} position. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")

    # High-motion context
    if high_motion > 0:
        lines.append(
            f"The system also identified {high_motion} high-motion work segment(s) — periods of "
            f"sustained physical exertion that, over a full shift, contribute to overall fatigue load.\n"
        )

    # Recommendations
    lines.append("### Recommended Interventions\n")
    if rework_events:
        lines.append(
            "- **Task rotation:** Alternate between different work zones every 30-45 minutes "
            "to distribute physical load across muscle groups and reduce zone-specific strain."
        )
        lines.append(
            "- **Micro-breaks:** Schedule 2-minute recovery breaks after each sustained high-intensity "
            "work period to prevent cumulative fatigue."
        )
    if near_miss_events:
        lines.append(
            "- **Posture coaching:** Review proper body mechanics for low-level brickwork and "
            "overhead tasks at the next toolbox talk. Consider kneeling pads or step platforms "
            "to reduce extreme postures."
        )
    if not rework_events and not near_miss_events:
        lines.append(
            "- Continue current work practices. Monitor for posture patterns as the shift progresses "
            "and fatigue accumulates."
        )

    return "\n".join(lines)


def _rule_based_productivity(events: List[dict], metrics: dict) -> str:
    """Generate rule-based productivity section."""
    prod = metrics.get("productivity", {})
    score = prod.get("score", "N/A")
    total = prod.get("total_min", 0)
    direct_min = prod.get("direct_min", 0)
    contrib_min = prod.get("contributory_min", 0)
    noncontrib_min = prod.get("noncontributory_min", 0)

    if total > 0:
        direct_pct = (direct_min / total) * 100
        contrib_pct = (contrib_min / total) * 100
        noncontrib_pct = (noncontrib_min / total) * 100
    else:
        direct_pct = contrib_pct = noncontrib_pct = 0

    sustained = [e for e in events if e.get("type") == "sustained_work"]
    idle_events = sorted(
        [e for e in events if e["type"] == "idle_streak"],
        key=lambda e: e.get("contributing_signals", {}).get("duration_sec", 0),
        reverse=True,
    )
    transitions = [e for e in events if e.get("type") == "task_transition"]

    lines = []

    # Opening narrative
    if score != "N/A" and isinstance(score, (int, float)):
        if score >= 70:
            verdict = "a productive shift"
        elif score >= 50:
            verdict = "a moderately productive shift"
        else:
            verdict = "a shift with significant productivity headroom"
    else:
        verdict = "this shift"

    lines.append(f"**Productivity Score: {score}/100**\n")
    lines.append(
        f"Overall, this was {verdict}. The analysis covers approximately {total:.0f} minutes "
        f"of recorded footage from this session.\n"
    )

    # Time breakdown in plain English
    lines.append("### Work Time Breakdown\n")
    lines.append(
        f"Of the {total:.0f} minutes analysed, the worker spent approximately **{direct_min:.0f} minutes "
        f"({direct_pct:.0f}%)** in direct productive work — activities such as brick laying, mortar "
        f"application, and material handling that directly advance the build. A further "
        f"**{contrib_min:.0f} minutes ({contrib_pct:.0f}%)** went to contributory tasks such as measuring, "
        f"inspection, and repositioning between work areas. The remaining "
        f"**{noncontrib_min:.0f} minutes ({noncontrib_pct:.0f}%)** was noncontributory time — "
        f"rest breaks, inactivity, or wait periods.\n"
    )

    label_cov = prod.get("label_coverage_pct", 0)
    if label_cov > 0:
        lines.append(
            f"*These figures are based on Gemini activity classification covering {label_cov:.0f}% "
            f"of frames, with signal-based estimation for the remainder.*\n"
        )

    # Activity breakdown table
    breakdown = prod.get("activity_breakdown", {})
    if breakdown:
        lines.append("### Activity Breakdown\n")
        lines.append("| Activity | Time (min) |")
        lines.append("|----------|------------|")
        for activity, mins in sorted(breakdown.items(), key=lambda x: -x[1]):
            if mins < 0.1:
                continue
            lines.append(f"| {activity.replace('_', ' ').title()} | {mins:.1f} |")
        lines.append("")

    # Sustained work — productive highlights
    if sustained:
        lines.append("### Productive Highlights\n")
        total_work = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in sustained
        )
        lines.append(
            f"The shift included {len(sustained)} sustained productive period(s) totalling "
            f"{total_work/60:.0f} minutes of uninterrupted focused work:\n"
        )
        for e in sustained[:5]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            act = e.get("contributing_signals", {}).get("primary_activity", "active work")
            sev_desc = {"high": "long", "med": "solid", "low": "brief"}.get(e.get("severity", "low"), "")
            lines.append(
                f"- At {e['start_time_fmt']}, the worker entered a {sev_desc} {dur/60:.1f}-minute "
                f"focused run of {act.replace('_', ' ')} without significant interruption. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")

    # Idle periods
    if idle_events:
        lines.append("### Inactivity & Gaps\n")
        total_idle = sum(
            e.get("contributing_signals", {}).get("duration_sec", 0) for e in idle_events
        )
        lines.append(
            f"The worker was inactive for a total of approximately {total_idle/60:.1f} minutes "
            f"across {len(idle_events)} period(s). These gaps may reflect scheduled rest breaks, "
            f"waiting for materials, or brief workflow disruptions:\n"
        )
        for e in idle_events[:3]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            sev = e.get("severity", "low")
            concern = " — this duration warrants review" if sev in ("med", "high") else ""
            lines.append(
                f"- At {e['start_time_fmt']}, the worker was inactive for {dur:.0f} seconds{concern}. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")

    # Task transitions
    if transitions:
        lines.append("### Work Phase Changes\n")
        lines.append(
            f"{len(transitions)} work phase change(s) were detected during the shift, "
            f"indicating shifts between different activity categories:\n"
        )
        for e in transitions[:4]:
            sigs = e.get("contributing_signals", {})
            from_act = sigs.get("from_activity", "previous task")
            to_act = sigs.get("to_activity", "next task")
            trigger = sigs.get("trigger", "signal")
            if trigger == "label":
                desc = (f"the worker transitioned from {from_act.replace('_', ' ')} "
                        f"to {to_act.replace('_', ' ')}")
            else:
                desc = "a significant shift in motion pattern and scene composition was detected"
            lines.append(
                f"- At {e['start_time_fmt']}, {desc}. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")

    return "\n".join(lines)


def _rule_based_quality(events: List[dict], metrics: dict) -> str:
    """Generate rule-based quality section."""
    qual = metrics.get("quality", {})
    score = qual.get("score", "N/A")
    verify_events = [e for e in events if e["type"] == "verification_moment"]
    rework_events = [e for e in events if e["type"] == "rework_proxy"]
    sustained_events = [e for e in events if e["type"] == "sustained_work"]

    lines = []

    # Opening
    if score != "N/A" and isinstance(score, (int, float)):
        if score >= 80:
            quality_verdict = "strong quality indicators"
        elif score >= 60:
            quality_verdict = "moderate quality signals with some areas to watch"
        else:
            quality_verdict = "quality concerns that warrant a physical site inspection"
    else:
        quality_verdict = "mixed quality signals"

    lines.append(f"**Quality Score: {score}/100**\n")
    lines.append(
        f"Today's session showed {quality_verdict}. The score reflects the balance between "
        f"focused uninterrupted work (positive), deliberate quality checks (positive), and "
        f"return-to-zone activity that may indicate corrections were needed (negative).\n"
    )

    # Sustained work — positive quality signal
    if sustained_events:
        lines.append("### Focused Work Periods\n")
        lines.append(
            f"{len(sustained_events)} sustained work period(s) were recorded — these represent "
            f"windows of uninterrupted, focused activity that tend to produce the most consistent "
            f"output quality in masonry work:\n"
        )
        for e in sustained_events[:5]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            act = e.get("contributing_signals", {}).get("primary_activity", "active work")
            lines.append(
                f"- At {e['start_time_fmt']}, the worker maintained {dur/60:.1f} minutes of "
                f"focused {act.replace('_', ' ')} without significant interruption. "
                f"This section of work is likely to reflect consistent quality. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")

    # Verification moments — positive
    if verify_events:
        lines.append("### Quality Checks & Inspection\n")
        lines.append(
            f"{len(verify_events)} verification moment(s) were detected — points where the worker "
            f"deliberately slowed down or paused to measure, check alignment, or inspect their work. "
            f"This is a positive quality behaviour:\n"
        )
        for e in verify_events[:5]:
            dur = e.get("contributing_signals", {}).get("duration_sec", 0)
            trigger = e.get("contributing_signals", {}).get("trigger", "signal")
            method = "Gemini activity classification" if trigger == "label" else "motion and depth signals"
            lines.append(
                f"- At {e['start_time_fmt']}, the worker paused for {dur:.0f} seconds, "
                f"consistent with measuring or inspecting their work (detected via {method}). "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")

    # Rework — concern
    if rework_events:
        lines.append("### Potential Rework Areas\n")
        lines.append(
            f"{len(rework_events)} area(s) were flagged where the worker returned to a previously "
            f"worked zone after a gap of 60+ seconds and resumed high-intensity activity. This pattern "
            f"may indicate the worker needed to adjust a brick's position, re-apply mortar, or "
            f"correct alignment. A physical inspection of these wall sections is recommended:\n"
        )
        for e in rework_events[:3]:
            sigs = e.get("contributing_signals", {})
            region = sigs.get("spatial_region", "?")
            gap = sigs.get("gap_sec", 0)
            lines.append(
                f"- At {e['start_time_fmt']}, the worker returned to zone {region} after a "
                f"{gap:.0f}-second absence and resumed intensive work in the same area. "
                f"Check this wall section for alignment, mortar consistency, and brick seating. "
                f"[{e['event_id']} @ {e['start_time_fmt']}]"
            )
        lines.append("")

    if not any([sustained_events, verify_events, rework_events]):
        lines.append(
            "No quality-specific signals were detected in this session. "
            "Run in augmented mode with Gemini enabled for deeper quality analysis "
            "including activity classification and inspection moment detection."
        )

    return "\n".join(lines)
