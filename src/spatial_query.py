"""
spatial_query.py — Component 3: Adaptive spatial query loop.
Forces correct VLM attention by localizing first, zooming in, then re-querying.
Budget-enforced, runs on top-K events only.
"""
import os
import json
import logging
import time
from typing import List, Optional

from . import config
from . import video_io

log = logging.getLogger(__name__)


class GeminiBudgetTracker:
    """Track Gemini API call budget."""

    def __init__(self, budget: int):
        self.budget = budget
        self.used = 0

    @property
    def remaining(self):
        return self.budget - self.used

    def consume(self) -> bool:
        """Try to consume one API call. Returns False if budget exhausted."""
        if self.remaining <= 0:
            log.warning(f"Gemini budget exhausted ({self.used}/{self.budget})")
            return False
        self.used += 1
        return True

    def __repr__(self):
        return f"GeminiBudgetTracker(used={self.used}/{self.budget})"


def _get_gemini_model():
    """Get configured Gemini model."""
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(config.GEMINI_MODEL)


def _call_gemini_with_image(model, image_path: str, prompt: str,
                             timeout: int = None) -> Optional[str]:
    """Call Gemini with an image and prompt. Returns response text or None."""
    if timeout is None:
        timeout = config.SPATIAL_QUERY_TIMEOUT

    try:
        import PIL.Image
        img = PIL.Image.open(image_path)

        response = model.generate_content(
            [prompt, img],
            generation_config={"temperature": 0.1, "max_output_tokens": 1024},
        )

        text = None
        try:
            text = response.text
        except ValueError as ve:
            log.error(f"Gemini spatial query response blocked: {ve}")
        if text and text.strip():
            return text.strip()
    except Exception as e:
        log.error(f"Gemini spatial query FAILED: {type(e).__name__}: {e}")

    return None


def _parse_json_response(text: str) -> Optional[dict]:
    """Parse JSON from Gemini response, handling markdown fences."""
    if text is None:
        return None

    # Strip markdown fences if present
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        clean = "\n".join(lines)

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Try to find JSON object in response
        import re
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', clean)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def run_spatial_queries(
    events: List[dict],
    all_keyframes: List[dict],
    video_paths: dict,
    output_dir: str,
    tracker: GeminiBudgetTracker,
    top_k: int = None,
) -> List[dict]:
    """
    Run spatial query loop on top-K events by severity.

    For each event:
    1. Localization pass — ask Gemini for bounding boxes
    2. Crop and re-query — zoom into each bbox
    3. Consistency voting — if disagreements
    4. Fallback — use sidecar heuristics if budget/failure

    Returns updated events with spatial query results.
    """
    if top_k is None:
        top_k = config.SPATIAL_QUERY_K

    # Sort events by severity (high first) and take top-K
    severity_order = {"high": 0, "med": 1, "low": 2}
    sorted_events = sorted(events, key=lambda e: severity_order.get(e.get("severity", "low"), 2))
    target_events = sorted_events[:top_k]

    if not target_events:
        log.info("No events to run spatial queries on")
        return events

    # Build keyframe lookup
    kf_lookup = {}
    for kf in all_keyframes:
        kf_lookup[kf["frame_id"]] = kf

    model = None
    try:
        model = _get_gemini_model()
    except Exception as e:
        log.warning(f"Cannot initialize Gemini for spatial queries: {e}")
        return events

    crops_dir = os.path.join(output_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)

    target_ids = {e["event_id"] for e in target_events}
    spatial_results = {}

    for event in target_events:
        if tracker.remaining <= 0:
            log.warning("Budget exhausted, stopping spatial queries")
            break

        eid = event["event_id"]

        # Find the best keyframe for this event
        frame_path = None
        frame_kf = None
        for kf_path in event.get("evidence", {}).get("keyframe_paths", []):
            full_path = os.path.join(output_dir, kf_path)
            if os.path.exists(full_path):
                frame_path = full_path
                # Find matching keyframe
                for kf in all_keyframes:
                    if kf.get("frame_path") == kf_path:
                        frame_kf = kf
                        break
                break

        if frame_path is None:
            log.debug(f"No frame found for event {eid}, skipping spatial query")
            continue

        # Step 1: Localization pass
        if not tracker.consume():
            break

        localization_prompt = (
            'Return a JSON object with bounding boxes (normalized 0-1 xywh coordinates) for: '
            'hands, primary_tool, work_surface, hazard_edge. For each include confidence (0-1). '
            'If not visible set to null. Return ONLY valid JSON, no other text, no markdown fences.'
        )

        loc_response = _call_gemini_with_image(model, frame_path, localization_prompt)
        loc_data = _parse_json_response(loc_response)

        if loc_data is None:
            # Retry once with stricter prompt
            if tracker.consume():
                stricter_prompt = (
                    'You MUST return ONLY a JSON object. No explanation. Format: '
                    '{"hands": {"bbox": [x,y,w,h], "confidence": 0.8}, '
                    '"primary_tool": null, "work_surface": null, "hazard_edge": null}'
                )
                loc_response = _call_gemini_with_image(model, frame_path, stricter_prompt)
                loc_data = _parse_json_response(loc_response)

            if loc_data is None:
                log.debug(f"Localization failed for {eid}, using sidecar fallback")
                spatial_results[eid] = _fallback_result(event, frame_kf)
                continue

        # Step 2: Crop and re-query for each non-null bbox
        gemini_passes = []
        crop_paths = []

        for obj_name in ["hands", "primary_tool", "work_surface", "hazard_edge"]:
            obj_data = loc_data.get(obj_name)
            if obj_data is None or not isinstance(obj_data, dict):
                continue

            bbox = obj_data.get("bbox")
            obj_conf = obj_data.get("confidence", 0)

            if bbox is None or obj_conf < config.SPATIAL_QUERY_MIN_CONF:
                continue

            if not tracker.consume():
                break

            # Extract and save crop
            frame = video_io.extract_frame_at_time(
                video_paths.get(event["video_file"], ""),
                event["start_time_sec"]
            )
            if frame is None:
                continue

            crop_filename = f"{event['event_id']}_{obj_name}.jpg"
            crop_path = os.path.join(crops_dir, crop_filename)

            saved = video_io.save_crop(frame, bbox, crop_path)
            if saved is None:
                continue

            crop_paths.append(os.path.relpath(crop_path, output_dir))

            # Re-query crop
            crop_prompt = (
                'In this cropped construction site image: '
                'Is the hand in contact with or within approximately 10cm of the tool? '
                'Is a hazard boundary visible? '
                'Estimate distance relationship: touching / very_close / near / far. '
                'Return ONLY valid JSON: '
                '{"contact": true, "proximity": "near", "hazard_visible": false, "confidence": 0.8}'
            )

            crop_response = _call_gemini_with_image(model, crop_path, crop_prompt)
            crop_data = _parse_json_response(crop_response)

            if crop_data:
                gemini_passes.append({
                    "object": obj_name,
                    "bbox": bbox,
                    "crop_path": os.path.relpath(crop_path, output_dir),
                    "result": crop_data,
                })

        # Step 3: Build consensus
        consensus = _build_consensus(gemini_passes)

        # Step 4: Consistency voting (if low confidence)
        if consensus.get("confidence", 0) < 0.6 and tracker.remaining >= 2:
            # Sample adjacent frames
            adj_results = _query_adjacent_frames(
                model, tracker, event, video_paths, output_dir, crops_dir
            )
            if adj_results:
                gemini_passes.extend(adj_results)
                consensus = _build_consensus(gemini_passes)

        spatial_results[eid] = {
            "frame_id": frame_kf["frame_id"] if frame_kf else "",
            "timestamp_sec": event["start_time_sec"],
            "query_type": event["type"],
            "localization_bbox": loc_data,
            "crop_paths": crop_paths,
            "gemini_passes": gemini_passes,
            "consensus_result": consensus,
            "confidence": consensus.get("confidence", 0),
            "llm_grounded": True,
        }

    # Update events with spatial query results
    for event in events:
        eid = event["event_id"]
        if eid in spatial_results:
            result = spatial_results[eid]
            event["spatial_query"] = result
            event["llm_grounded"] = result.get("llm_grounded", False)
            event["evidence"]["crop_paths"] = result.get("crop_paths", [])

            # Update confidence if spatial query confirms
            if result.get("confidence", 0) > 0.6:
                event["confidence"] = min(1.0, max(event["confidence"], result["confidence"]))

    log.info(f"Completed spatial queries for {len(spatial_results)} events "
             f"(budget: {tracker.used}/{tracker.budget})")

    return events


def _build_consensus(passes: List[dict]) -> dict:
    """Build consensus from multiple Gemini passes."""
    if not passes:
        return {"contact": False, "proximity": "far", "hazard_visible": False, "confidence": 0.0}

    contacts = []
    proximities = []
    hazards = []
    confidences = []

    for p in passes:
        result = p.get("result", {})
        if isinstance(result, dict):
            if "contact" in result:
                contacts.append(bool(result["contact"]))
            if "proximity" in result:
                proximities.append(str(result["proximity"]))
            if "hazard_visible" in result:
                hazards.append(bool(result["hazard_visible"]))
            if "confidence" in result:
                try:
                    confidences.append(float(result["confidence"]))
                except (ValueError, TypeError):
                    pass

    return {
        "contact": _majority_vote(contacts, False),
        "proximity": _majority_string(proximities, "far"),
        "hazard_visible": _majority_vote(hazards, False),
        "confidence": round(sum(confidences) / max(len(confidences), 1), 3),
    }


def _majority_vote(values: list, default: bool) -> bool:
    if not values:
        return default
    return sum(values) > len(values) / 2


def _majority_string(values: list, default: str) -> str:
    if not values:
        return default
    from collections import Counter
    return Counter(values).most_common(1)[0][0]


def _query_adjacent_frames(model, tracker, event, video_paths, output_dir, crops_dir):
    """Query up to 2 adjacent frames for consistency voting."""
    results = []
    video_path = video_paths.get(event.get("video_file", ""))
    if not video_path:
        return results

    offsets = [-2.0, 2.0]  # ±2 seconds
    for offset in offsets:
        if not tracker.consume():
            break

        adj_time = max(0, event["start_time_sec"] + offset)
        frame = video_io.extract_frame_at_time(video_path, adj_time)
        if frame is None:
            continue

        adj_path = os.path.join(crops_dir, f"{event['event_id']}_adj_{offset:.0f}s.jpg")
        video_io.save_frame(frame, adj_path)

        prompt = (
            'In this construction site image: '
            'Is a hand in contact with or near a tool? '
            'Is a hazard boundary visible? '
            'Return ONLY valid JSON: '
            '{"contact": true, "proximity": "near", "hazard_visible": false, "confidence": 0.8}'
        )

        response = _call_gemini_with_image(model, adj_path, prompt)
        data = _parse_json_response(response)

        if data:
            results.append({
                "object": "adjacent_frame",
                "crop_path": os.path.relpath(adj_path, output_dir),
                "result": data,
            })

    return results


def _fallback_result(event: dict, keyframe: Optional[dict]) -> dict:
    """Produce fallback result using sidecar heuristics only."""
    return {
        "frame_id": keyframe["frame_id"] if keyframe else "",
        "timestamp_sec": event.get("start_time_sec", 0),
        "query_type": event["type"],
        "localization_bbox": {},
        "crop_paths": [],
        "gemini_passes": [],
        "consensus_result": {
            "contact": False, "proximity": "unknown",
            "hazard_visible": False, "confidence": 0.0,
        },
        "confidence": 0.0,
        "llm_grounded": False,
    }
