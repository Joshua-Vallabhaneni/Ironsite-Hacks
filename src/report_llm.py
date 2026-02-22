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

SYSTEM_PROMPT = (
    "You are a senior construction site supervisor writing a detailed daily briefing "
    "for a project manager. This report will also be read aloud by a voice AI assistant "
    "to brief the manager verbally. "
    "Write in clear, professional English using full sentences and paragraphs — "
    "not raw data dumps. Describe what was actually happening on site: explain each "
    "scenario in plain language, what the worker was doing, what the observation means "
    "in a real construction context, and what action the manager should take. "
    "For every specific event you reference, cite it as [EVENT_ID @ HH:MM:SS]. "
    "Only reference events explicitly present in the provided data. "
    "When data is limited, explain what the available signals suggest rather than refusing to comment. "
    "Use language a non-technical project manager can understand and act on immediately."
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
        f"Write 4-6 headline bullet points for the front page of a construction site daily report. "
        f"This will be read by a project manager and spoken aloud by a voice assistant. "
        f"Each headline must be a complete, informative sentence that tells a story — "
        f"not just 'event detected' but what it means for the project and what to do about it.\n\n"
        f"Event type context for writing headlines:\n"
        f"  ppe_violation = worker observed without protective gloves during active masonry work\n"
        f"  rework_proxy = worker returned to same area after 60+ seconds away (possible rework or adjustment)\n"
        f"  sustained_work = worker maintained focused productive activity for 60+ seconds continuously\n"
        f"  near_miss_proxy = worker using a tool in a high-risk posture (crouching/reaching overhead)\n"
        f"  idle_streak = worker was stationary and inactive (rest, wait, or disruption)\n"
        f"  task_transition = worker shifted between different types of work activity\n"
        f"  verification_moment = worker paused to inspect, measure, or check their work\n\n"
        f"Top events:\n{events_json}\n\n"
        f"Scores — Safety: {metrics.get('safety', {}).get('score', 'N/A')}/100, "
        f"Ergonomics: {metrics.get('ergonomics', {}).get('score', 'N/A')}/100, "
        f"Productivity: {metrics.get('productivity', {}).get('score', 'N/A')}/100, "
        f"Quality: {metrics.get('quality', {}).get('score', 'N/A')}/100\n\n"
        f"Format as markdown bullet points. Each bullet must be a full sentence. "
        f"Cite relevant events as [EVENT_ID @ HH:MM:SS]. Lead with the most important finding."
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

    EVENT_GLOSSARY = (
        "Event type definitions — use these to write detailed scenario descriptions:\n"
        "  ppe_violation: worker observed without protective gloves during active masonry hand work\n"
        "  near_miss_proxy: worker using a tool while crouching or reaching overhead — elevated injury risk\n"
        "  occlusion_critical: sustained visual obstruction during high-intensity work; worker in confined area\n"
        "  approach_hazard_proxy: camera moving toward a depth discontinuity — worker near a ledge or edge\n"
        "  rework_proxy: worker returned to same area after 60+ second gap — possible adjustment or redo\n"
        "  idle_streak: worker stationary with low activity — rest, material wait, or disruption\n"
        "  task_transition: worker shifted work category (e.g. brick laying → repositioning)\n"
        "  sustained_work: worker maintained focused productive activity for 60+ consecutive seconds\n"
        "  verification_moment: worker paused to measure, inspect, or check alignment — positive quality signal\n"
    )

    section_prompts = {
        "safety": (
            f"Write the SAFETY BRIEFING section of a construction site daily report for a project manager.\n\n"
            f"{EVENT_GLOSSARY}\n"
            f"Safety Score: {metrics.get('safety', {}).get('score', 'N/A')}/100\n\n"
            f"Events:\n{events_json}\n\n"
            f"Write 3-5 paragraphs. Open with a 1-2 sentence summary of today's safety picture. "
            f"Then cover PPE compliance (describe glove violations as scenarios — what was the worker doing, "
            f"how long, what is the risk), tool handling risks (near_miss_proxy — describe posture and activity), "
            f"and fall/obstruction risk (approach_hazard, occlusion_critical). "
            f"For each event, explain the scenario in plain English and cite as [EVENT_ID @ HH:MM:SS]. "
            f"Close with 2-3 concrete recommended actions for the manager to take before tomorrow's shift. "
            f"Write in full sentences. This will be spoken aloud to the manager."
        ),
        "ergonomics": (
            f"Write the ERGONOMICS & WORKER WELFARE section of a construction site daily report.\n\n"
            f"{EVENT_GLOSSARY}\n"
            f"Ergonomics Score: {metrics.get('ergonomics', {}).get('score', 'N/A')}/100\n"
            f"High-motion work segments detected: {metrics.get('ergonomics', {}).get('high_motion_segments', 0)}\n\n"
            f"Events:\n{events_json}\n\n"
            f"Write 3-4 paragraphs. Open with a 1-2 sentence summary of today's physical strain level. "
            f"For rework_proxy events, describe each as a repetitive motion scenario — "
            f"the worker returned to the same physical area and repeated the same movements, "
            f"stressing the same muscle groups. Include the time gap between return visits. "
            f"For near_miss_proxy events, describe them as posture stress events — "
            f"prolonged crouching or overhead reaching with tools is hard on joints over a full shift. "
            f"Note if events cluster early or late (fatigue pattern). "
            f"Cite each event as [EVENT_ID @ HH:MM:SS]. "
            f"Close with specific recommended interventions: task rotation schedule, micro-break timing, "
            f"posture coaching focus areas. Write in full sentences."
        ),
        "productivity": (
            f"Write the PRODUCTIVITY & FLOW section of a construction site daily report.\n\n"
            f"{EVENT_GLOSSARY}\n"
            f"Productivity Score: {metrics.get('productivity', {}).get('score', 'N/A')}/100\n\n"
            f"Productivity breakdown (from keyframe analysis — no individual event IDs needed for these figures):\n"
            f"{json.dumps(metrics.get('productivity', {}), indent=2, default=str)}\n\n"
            f"Events:\n{events_json}\n\n"
            f"Write 3-5 paragraphs. Open with 1-2 sentences: was this a productive shift? "
            f"Report the Direct/Contributory/Noncontributory time split in plain English "
            f"(e.g. 'The worker spent approximately X minutes in direct productive masonry work'). "
            f"For sustained_work events, describe them as the productive highlights of the shift — "
            f"when was the worker most focused, what were they doing, how long did it last. "
            f"Cite each as [EVENT_ID @ HH:MM:SS]. "
            f"For idle_streak events, describe each gap — duration, timing, likely cause. "
            f"Cite as [EVENT_ID @ HH:MM:SS]. "
            f"For task_transition events, describe what changed and when. "
            f"Close with a practical recommendation for improving output tomorrow. "
            f"Write in full sentences. This will be spoken aloud to the manager."
        ),
        "quality": (
            f"Write the QUALITY & PROGRESS section of a construction site daily report.\n\n"
            f"{EVENT_GLOSSARY}\n"
            f"Quality Score: {metrics.get('quality', {}).get('score', 'N/A')}/100\n\n"
            f"Events:\n{events_json}\n\n"
            f"Write 3-4 paragraphs. Open with 1-2 sentences summarising the quality picture. "
            f"For sustained_work events, frame these as evidence of focused quality output — "
            f"uninterrupted work produces more consistent results; describe the activity and duration. "
            f"Cite each as [EVENT_ID @ HH:MM:SS]. "
            f"For verification_moment events, describe these positively — "
            f"the worker deliberately paused to check, measure, or inspect their work. "
            f"Cite each as [EVENT_ID @ HH:MM:SS]. "
            f"For rework_proxy events, flag these as quality concerns — "
            f"describe the scenario (worker returned to an area they had already worked, "
            f"which may mean a brick needed repositioning or mortar needed correction) "
            f"and what a supervisor should physically check at that section of wall. "
            f"Cite each as [EVENT_ID @ HH:MM:SS]. "
            f"Close with an overall quality verdict and what to inspect in the next session. "
            f"Write in full sentences."
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
