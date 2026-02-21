"""
report_llm.py — Gemini narrative generation with citation-enforcement system prompt.
Every claim must cite an event_id and timestamp from the sidecar.
"""
import os
import json
import logging
from typing import List, Optional

from . import config
from .spatial_query import GeminiBudgetTracker

log = logging.getLogger(__name__)

# Citation-enforcement system prompt (verbatim from spec)
SYSTEM_PROMPT = (
    "You are a construction site supervisor report writer. "
    "You may ONLY make claims about events present in the provided JSON sidecar. "
    "For every claim you make, you MUST include a citation in the format [EVENT_ID @ HH:MM:SS]. "
    "Do not infer, speculate, or add any observations not present in the sidecar. "
    "If you cannot support a claim with a cited event, omit it entirely."
)


def _get_gemini_model():
    """Get Gemini model configured with system prompt."""
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        config.GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )


def generate_narrative_section(
    section_name: str,
    events: List[dict],
    metrics: dict,
    all_keyframes: List[dict],
    tracker: GeminiBudgetTracker,
) -> str:
    """
    Generate a narrative section using Gemini, constrained to cite sidecar evidence.
    Returns markdown text for the section.
    """
    if not tracker.consume():
        log.warning(f"Budget exhausted, skipping narrative for {section_name}")
        return f"*[Narrative generation skipped — Gemini budget exhausted]*\n"

    try:
        model = _get_gemini_model()
    except Exception as e:
        log.warning(f"Cannot init Gemini for narrative: {e}")
        return f"*[Narrative generation failed — {e}]*\n"

    # Build evidence context
    relevant_events = _filter_events_for_section(section_name, events)
    events_json = json.dumps(relevant_events, indent=2, default=str)

    prompt = _build_section_prompt(section_name, events_json, metrics)

    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 2048},
        )
        text = None
        try:
            text = response.text
        except ValueError as ve:
            log.error(f"Gemini response blocked for {section_name}: {ve}")
        if text and text.strip():
            log.info(f"Gemini narrative OK for section={section_name} ({len(text)} chars)")
            return text.strip()
    except Exception as e:
        log.error(f"Gemini narrative FAILED for {section_name}: {type(e).__name__}: {e}")

    return f"*[Narrative generation failed for {section_name}]*\n"


def generate_headlines(
    events: List[dict],
    metrics: dict,
    tracker: GeminiBudgetTracker,
) -> str:
    """Generate top headlines for the front page."""
    if not tracker.consume():
        return _fallback_headlines(events, metrics)

    try:
        model = _get_gemini_model()
    except Exception as e:
        return _fallback_headlines(events, metrics)

    # Top events by severity
    top_events = sorted(events, key=lambda e: {"high": 0, "med": 1, "low": 2}.get(e.get("severity", "low"), 2))[:10]
    events_json = json.dumps(top_events, indent=2, default=str)

    prompt = (
        f"Based on the following construction site events and metrics, "
        f"write 3-6 concise headline bullet points for a daily site report front page. "
        f"Each headline MUST cite an event in [EVENT_ID @ HH:MM:SS] format.\n\n"
        f"Events:\n{events_json}\n\n"
        f"Metrics: Safety={metrics.get('safety', {}).get('score', 'N/A')}/100, "
        f"Ergonomics={metrics.get('ergonomics', {}).get('score', 'N/A')}/100, "
        f"Productivity={metrics.get('productivity', {}).get('score', 'N/A')}/100, "
        f"Quality={metrics.get('quality', {}).get('score', 'N/A')}/100\n\n"
        f"Format as markdown bullet points. Be specific and evidence-backed."
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.3, "max_output_tokens": 1024},
        )
        text = None
        try:
            text = response.text
        except ValueError as ve:
            log.error(f"Gemini headlines response blocked: {ve}")
        if text and text.strip():
            log.info(f"Gemini headlines OK ({len(text)} chars)")
            return text.strip()
    except Exception as e:
        log.error(f"Gemini headline generation FAILED: {type(e).__name__}: {e}")

    return _fallback_headlines(events, metrics)


def generate_baseline_summary(
    frames_chunk: List[dict],
    chunk_index: int,
    tracker: GeminiBudgetTracker,
) -> str:
    """
    Generate a summary for a chunk of uniformly sampled frames (baseline mode).
    No sidecar, no event data — just frames described by Gemini.
    """
    if not tracker.consume():
        return ""

    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return ""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(config.GEMINI_MODEL)
    except Exception as e:
        return ""

    # Build description of frames (send frame paths as context)
    frames_desc = []
    images = []


    for i, fc in enumerate(frames_chunk):
        frames_desc.append(f"Frame {i+1}: timestamp={fc.get('timestamp_fmt', 'N/A')}, "
                          f"video={fc.get('video_file', 'N/A')}")
        # Load image if path exists
        frame_path = fc.get("full_frame_path", "")
        if frame_path and os.path.exists(frame_path):
            try:
                import PIL.Image
                img = PIL.Image.open(frame_path)
                images.append(img)
            except Exception:
                pass

    frames_text = "\n".join(frames_desc)

    prompt = (
        f"You are analyzing construction site footage. "
        f"Here are {len(frames_chunk)} frames from the work day.\n\n"
        f"{frames_text}\n\n"
        f"Describe what activities you observe, any safety concerns, "
        f"worker productivity patterns, and quality of work visible. "
        f"Be specific about what you see in each frame. "
        f"Include timestamps for each observation."
    )

    try:
        content = [prompt] + images if images else [prompt]
        response = model.generate_content(
            content,
            generation_config={"temperature": 0.3, "max_output_tokens": 2048},
        )
        text = None
        try:
            text = response.text
        except ValueError as ve:
            log.error(f"Gemini baseline chunk {chunk_index} response blocked: {ve}")
        if text and text.strip():
            return text.strip()
    except Exception as e:
        log.error(f"Gemini baseline chunk {chunk_index} FAILED: {type(e).__name__}: {e}")

    return ""


def merge_baseline_summaries(
    summaries: List[str],
    tracker: GeminiBudgetTracker,
) -> str:
    """Merge partial baseline summaries into a final report."""
    if not tracker.consume():
        return "\n\n---\n\n".join(s for s in summaries if s)

    try:
        model = _get_gemini_model()
    except Exception:
        return "\n\n---\n\n".join(s for s in summaries if s)

    combined = "\n\n---\n\n".join(f"[Segment {i+1}]\n{s}" for i, s in enumerate(summaries) if s)

    prompt = (
        f"Combine the following construction site observation segments into a cohesive daily report. "
        f"Organize into these sections:\n"
        f"1. Top Headlines (3-6 bullets)\n"
        f"2. Safety observations\n"
        f"3. Ergonomics concerns\n"
        f"4. Productivity & Flow analysis\n"
        f"5. Quality & Progress notes\n\n"
        f"Segments:\n{combined}\n\n"
        f"Write a professional site report in markdown format. "
        f"Include timestamps where mentioned in the segments."
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 4096},
        )
        text = None
        try:
            text = response.text
        except ValueError as ve:
            log.error(f"Gemini baseline merge response blocked: {ve}")
        if text and text.strip():
            return text.strip()
    except Exception as e:
        log.error(f"Gemini baseline merge FAILED: {type(e).__name__}: {e}")

    return combined


def _filter_events_for_section(section_name: str, events: List[dict]) -> List[dict]:
    """Filter events relevant to a report section."""
    section_map = {
        "safety": [
            "near_miss_proxy", "occlusion_critical",
            "approach_hazard_proxy", "ppe_violation",
        ],
        "ergonomics": ["rework_proxy"],
        "productivity": ["idle_streak", "task_transition", "sustained_work"],
        "quality": ["verification_moment", "rework_proxy", "sustained_work"],
    }

    relevant_types = section_map.get(section_name.lower(), [])
    if not relevant_types:
        return events[:20]  # return top 20 if no filter

    return [e for e in events if e.get("type") in relevant_types]


def _build_section_prompt(section_name: str, events_json: str, metrics: dict) -> str:
    """Build the prompt for a specific report section."""
    section_prompts = {
        "safety": (
            f"Write the SAFETY DESK section of a construction daily report. "
            f"First, report any ppe_violation events under a 'PPE Compliance' heading. "
            f"Then organize remaining findings under: Falls, Struck-By, Caught-In/Between, Electrical. "
            f"For each subsection: report exposure minutes, event count, and top 3 events. "
            f"Each event citation must be in format [EVENT_ID @ HH:MM:SS].\n\n"
            f"Safety Score: {metrics.get('safety', {}).get('score', 'N/A')}/100\n\n"
            f"Events:\n{events_json}"
        ),
        "ergonomics": (
            f"Write the ERGONOMICS section of a construction daily report. "
            f"Include high-risk minutes, peak strain events with timestamps, "
            f"and recommended interventions. Cite events as [EVENT_ID @ HH:MM:SS].\n\n"
            f"Ergonomics Score: {metrics.get('ergonomics', {}).get('score', 'N/A')}/100\n\n"
            f"Events:\n{events_json}"
        ),
        "productivity": (
            f"Write the PRODUCTIVITY & FLOW section. Include Direct/Contributory/"
            f"Noncontributory breakdown in minutes and percentages. "
            f"List biggest blockers with timestamps. "
            f"Identify the best continuous-flow window.\n\n"
            f"Productivity details: {json.dumps(metrics.get('productivity', {}), default=str)}\n\n"
            f"Events:\n{events_json}"
        ),
        "quality": (
            f"Write the QUALITY & PROGRESS section. "
            f"List sustained_work periods (these show productive focused work), "
            f"verification moments, and rework signals with timestamps. "
            f"Cite events as [EVENT_ID @ HH:MM:SS].\n\n"
            f"Quality Score: {metrics.get('quality', {}).get('score', 'N/A')}/100\n\n"
            f"Events:\n{events_json}"
        ),
    }

    return section_prompts.get(section_name.lower(), f"Write section: {section_name}\n\n{events_json}")


def _fallback_headlines(events: List[dict], metrics: dict) -> str:
    """Generate headlines without Gemini."""
    lines = []
    safety = metrics.get("safety", {}).get("score", "N/A")
    prod = metrics.get("productivity", {}).get("score", "N/A")

    high_events = [e for e in events if e.get("severity") == "high"]
    if high_events:
        e = high_events[0]
        lines.append(f"- ⚠️ {e['type'].replace('_', ' ').title()} detected "
                     f"[{e['event_id']} @ {e['start_time_fmt']}]")

    lines.append(f"- Safety Index: {safety}/100")
    lines.append(f"- Productivity Index: {prod}/100")
    lines.append(f"- Total events detected: {len(events)}")

    idle_events = [e for e in events if e.get("type") == "idle_streak"]
    if idle_events:
        total_idle = sum(e.get("contributing_signals", {}).get("duration_sec", 0) for e in idle_events)
        lines.append(f"- Cumulative idle time: {total_idle/60:.1f} minutes across {len(idle_events)} periods")

    verify = [e for e in events if e.get("type") == "verification_moment"]
    if verify:
        lines.append(f"- {len(verify)} quality verification moments observed")

    return "\n".join(lines)
