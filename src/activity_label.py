"""
activity_label.py — Gemini-powered frame-level activity classification.

Phase 2.5 of the pipeline: runs after sidecar construction, before event extraction.
Sends batches of uniformly-sampled keyframes to Gemini for semantic activity labeling,
overcoming YOLO/MediaPipe failures on construction-specific tools and gloved hands.

Labels are attached to enriched keyframes as `gemini_label` and used to:
  - Override `interaction_density` with domain-accurate values
  - Enable sustained_work and ppe_violation event detection
  - Drive activity-based productivity classification
  - Generate the activity timeline in the report
"""

import os
import re
import json
import logging
from typing import List, Dict, Optional

from . import config
from .spatial_query import GeminiBudgetTracker

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini prompt
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
You are analyzing egocentric construction headcam footage from a worker's point of view.
You will receive {n} frames numbered 1 through {n}. Analyze each frame independently.

Return ONLY a valid JSON array with exactly {n} objects, one per frame, in order.
Each object must contain:
  "frame"        : integer (1-based index matching the image order)
  "activity"     : one of ["brick_laying","mortar_application","measuring","inspection",
                            "material_handling","scaffolding","repositioning","idle","other"]
  "tool_held"    : one of ["trowel","level","hammer","drill","grinder","brush","none","unknown"]
  "ppe_hard_hat" : true, false, or "uncertain"
  "ppe_gloves"   : true, false, or "uncertain"
  "posture"      : one of ["standing","kneeling","crouching","reaching_overhead","other"]
  "confidence"   : float 0.0-1.0 (overall confidence in your classification of this frame)

Activity definitions:
  brick_laying       — actively placing or setting bricks/blocks
  mortar_application — spreading mortar or cement with a trowel or other tool
  measuring          — using a level, tape measure, or checking alignment/plumb
  inspection         — visually studying completed work without active tool use
  material_handling  — carrying, stacking, or organizing bricks or materials
  scaffolding        — climbing, adjusting, or working on/near scaffold structure
  repositioning      — walking or moving between work positions
  idle               — worker stationary and not actively working (resting, waiting)
  other              — none of the above

Notes:
  - If a frame is blurry or partially obscured, still classify to best ability with lower confidence.
  - ppe_hard_hat: true only if a safety helmet is clearly visible on the worker's head.
  - ppe_gloves: true only if protective gloves are clearly visible on the worker's hands.
  - Return ONLY the JSON array. No explanation. No markdown code fences.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def label_frames(
    enriched_keyframes: List[dict],
    output_dir: str,
    tracker: GeminiBudgetTracker,
) -> Dict[str, dict]:
    """
    Label a representative subset of keyframes with Gemini activity classification.

    Selects uniform-sample frames at ACTIVITY_LABEL_INTERVAL_SEC intervals per video,
    batches them, calls Gemini, then interpolates labels to nearby unlabeled frames.

    Args:
        enriched_keyframes: list of enriched keyframe dicts (frame_path must be set)
        output_dir: base output directory (frame_paths are relative to this)
        tracker: Gemini budget tracker

    Returns:
        dict mapping frame_id -> label dict with keys:
            activity, tool_held, ppe_hard_hat, ppe_gloves, posture, confidence
            (interpolated frames also have interpolated=True)
    """
    if not enriched_keyframes:
        return {}

    to_label = _select_frames_to_label(enriched_keyframes)
    if not to_label:
        sample = enriched_keyframes[:3]
        has_paths = [bool(kf.get("frame_path")) for kf in sample]
        has_reason = [kf.get("reason") for kf in sample]
        log.warning(
            f"No frames with saved frame_path available for activity labeling. "
            f"Sample frame_path present: {has_paths}, reasons: {has_reason}"
        )
        return {}

    log.info(
        f"Activity labeling: {len(to_label)} frames selected "
        f"from {len(enriched_keyframes)} total keyframes"
    )

    try:
        model = _get_gemini_model()
    except Exception as e:
        log.warning(f"Cannot initialize Gemini for activity labeling: {e}")
        return {}

    direct_labels: Dict[str, dict] = {}
    batch_size = config.ACTIVITY_LABEL_BATCH_SIZE
    total_batches = (len(to_label) + batch_size - 1) // batch_size

    for batch_start in range(0, len(to_label), batch_size):
        batch = to_label[batch_start : batch_start + batch_size]
        batch_num = batch_start // batch_size + 1

        if not tracker.consume():
            log.warning(
                f"Gemini budget exhausted at activity labeling batch "
                f"{batch_num}/{total_batches}"
            )
            break

        batch_labels = _label_batch(model, batch, output_dir)
        direct_labels.update(batch_labels)
        log.info(
            f"Activity labeling: batch {batch_num}/{total_batches} "
            f"— {len(batch_labels)}/{len(batch)} frames labeled"
        )

    log.info(f"Direct labels obtained: {len(direct_labels)} frames")

    all_labels = _interpolate_labels(direct_labels, enriched_keyframes)
    log.info(f"After interpolation: {len(all_labels)} frames have activity labels")

    _log_distribution(all_labels)
    return all_labels


def apply_labels_to_keyframes(
    enriched_keyframes: List[dict],
    labels: Dict[str, dict],
) -> None:
    """
    Apply activity labels to enriched keyframes in-place.

    For each labeled frame:
      - Attaches `gemini_label` dict
      - Overrides `interaction_density` when label confidence >= ACTIVITY_LABEL_CONF_THRESH
    """
    applied = 0
    overridden = 0

    for kf in enriched_keyframes:
        label = labels.get(kf["frame_id"])
        if label is None:
            continue

        kf["gemini_label"] = label
        applied += 1

        override = get_interaction_density_override(label)
        if override is not None:
            kf["interaction_density"] = override
            overridden += 1

    log.info(
        f"Applied {applied} activity labels; "
        f"overrode interaction_density on {overridden} frames"
    )


def get_interaction_density_override(label: Optional[dict]) -> Optional[float]:
    """
    Return an interaction_density override based on the activity label.
    Returns None if the label is missing or confidence is below threshold.
    """
    if not label:
        return None
    if label.get("confidence", 0) < config.ACTIVITY_LABEL_CONF_THRESH:
        return None
    return config.ACTIVITY_INTERACTION_MAP.get(label.get("activity", "other"))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _select_frames_to_label(enriched_keyframes: List[dict]) -> List[dict]:
    """
    Select one frame per ACTIVITY_LABEL_INTERVAL_SEC per video.
    Prefers uniform-sample frames; falls back to all frames if none have frame_path.
    """
    by_video: Dict[str, List[dict]] = {}
    for kf in enriched_keyframes:
        by_video.setdefault(kf.get("video_file", ""), []).append(kf)

    selected = []
    interval = config.ACTIVITY_LABEL_INTERVAL_SEC

    for _vid, kfs in by_video.items():
        candidates = [kf for kf in kfs
                      if kf.get("reason") == "uniform" and kf.get("frame_path")]
        if not candidates:
            candidates = [kf for kf in kfs if kf.get("frame_path")]
        if not candidates:
            continue

        candidates.sort(key=lambda x: x["timestamp_sec"])
        next_label_sec = 0.0
        for kf in candidates:
            if kf["timestamp_sec"] >= next_label_sec:
                selected.append(kf)
                next_label_sec = kf["timestamp_sec"] + interval

    return selected


def _label_batch(model, batch: List[dict], output_dir: str) -> Dict[str, dict]:
    """Send one batch of frames to Gemini; return frame_id -> label dict."""
    import PIL.Image

    images = []
    valid_kfs = []
    missing_paths = []

    for kf in batch:
        frame_path = kf.get("frame_path", "")
        full_path = os.path.join(output_dir, frame_path) if frame_path else ""
        if not full_path or not os.path.exists(full_path):
            missing_paths.append(full_path or "(no frame_path set)")
            continue
        try:
            img = PIL.Image.open(full_path).convert("RGB")  # convert ensures compatibility
            images.append(img)
            valid_kfs.append(kf)
        except Exception as e:
            log.warning(f"Cannot open frame {full_path}: {e}")

    if not images:
        log.warning(
            f"No images loaded for batch of {len(batch)} frames. "
            f"output_dir={output_dir!r}. "
            f"Missing/bad paths: {missing_paths[:3]}"
        )
        return {}

    n = len(images)
    prompt = _PROMPT_TEMPLATE.format(n=n)
    content = [prompt] + images

    try:
        response = model.generate_content(
            content,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": max(512, 200 * n),
            },
        )

        text = None
        try:
            text = response.text
        except ValueError as ve:
            log.warning(f"Gemini activity label response blocked: {ve}")
            return {}

        if not text or not text.strip():
            log.warning("Gemini returned empty response for activity labeling batch")
            return {}

        parsed = _parse_label_array(text.strip(), n)
        if parsed is None:
            log.warning(
                f"Could not parse activity labels from Gemini response "
                f"(batch n={n}). Preview: {text[:200]!r}"
            )
            return {}

        result: Dict[str, dict] = {}
        for entry in parsed:
            # Match by the "frame" field (1-based) when present, else by position
            raw_idx = entry.get("frame")
            if raw_idx is not None:
                try:
                    idx = int(raw_idx) - 1
                except (TypeError, ValueError):
                    idx = parsed.index(entry)
            else:
                idx = parsed.index(entry)

            if 0 <= idx < len(valid_kfs):
                result[valid_kfs[idx]["frame_id"]] = _normalize_label(entry)

        return result

    except Exception as e:
        log.warning(f"Gemini activity label batch failed: {type(e).__name__}: {e}")
        return {}


def _parse_label_array(text: str, expected_n: int) -> Optional[List[dict]]:
    """Parse a JSON array from Gemini response, tolerating common formatting issues."""
    clean = text.strip()

    # Strip markdown fences
    if clean.startswith("```"):
        lines = clean.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        clean = "\n".join(lines).strip()

    # Direct parse
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list) and v:
                    return v
    except json.JSONDecodeError:
        pass

    # Find array via regex
    match = re.search(r"\[[\s\S]*\]", clean)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def _normalize_label(raw: dict) -> dict:
    """Validate and normalize a single activity label dict from Gemini."""
    VALID_ACTIVITIES = {
        "brick_laying", "mortar_application", "measuring", "inspection",
        "material_handling", "scaffolding", "repositioning", "idle", "other",
    }
    VALID_TOOLS = {
        "trowel", "level", "hammer", "drill", "grinder", "brush", "none", "unknown",
    }
    VALID_POSTURES = {
        "standing", "kneeling", "crouching", "reaching_overhead", "other",
    }

    activity = str(raw.get("activity", "other")).lower().strip()
    if activity not in VALID_ACTIVITIES:
        activity = "other"

    tool = str(raw.get("tool_held", "unknown")).lower().strip()
    if tool not in VALID_TOOLS:
        tool = "unknown"

    posture = str(raw.get("posture", "other")).lower().strip()
    if posture not in VALID_POSTURES:
        posture = "other"

    def _ppe(val) -> object:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            v = val.lower().strip()
            if v == "true":
                return True
            if v == "false":
                return False
        return "uncertain"

    try:
        confidence = float(raw.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "activity":     activity,
        "tool_held":    tool,
        "ppe_hard_hat": _ppe(raw.get("ppe_hard_hat")),
        "ppe_gloves":   _ppe(raw.get("ppe_gloves")),
        "posture":      posture,
        "confidence":   round(confidence, 3),
    }


def _interpolate_labels(
    direct_labels: Dict[str, dict],
    all_keyframes: List[dict],
) -> Dict[str, dict]:
    """
    Propagate direct labels to nearby unlabeled frames within ACTIVITY_LABEL_INTERP_SEC.
    Confidence decays linearly with distance from the nearest direct-labeled frame.
    Only interpolates within the same video.
    """
    if not direct_labels:
        return {}

    interp_sec = config.ACTIVITY_LABEL_INTERP_SEC
    result = dict(direct_labels)

    by_video: Dict[str, List[dict]] = {}
    for kf in all_keyframes:
        by_video.setdefault(kf.get("video_file", ""), []).append(kf)

    for _vid, kfs in by_video.items():
        kfs_sorted = sorted(kfs, key=lambda x: x["timestamp_sec"])

        labeled_in_vid = sorted(
            [
                (kf["timestamp_sec"], kf["frame_id"])
                for kf in kfs_sorted
                if kf["frame_id"] in direct_labels
            ],
            key=lambda x: x[0],
        )
        if not labeled_in_vid:
            continue

        for kf in kfs_sorted:
            if kf["frame_id"] in result:
                continue

            t = kf["timestamp_sec"]
            nearest_time, nearest_fid = min(labeled_in_vid, key=lambda x: abs(x[0] - t))
            gap = abs(nearest_time - t)

            if gap <= interp_sec:
                base = direct_labels[nearest_fid]
                decay = 1.0 - (gap / interp_sec)
                inherited_conf = round(base["confidence"] * decay * 0.85, 3)
                if inherited_conf >= 0.25:
                    result[kf["frame_id"]] = {
                        **base,
                        "confidence":   inherited_conf,
                        "interpolated": True,
                    }

    return result


def _log_distribution(labels: Dict[str, dict]) -> None:
    """Log activity distribution for direct-labeled frames."""
    from collections import Counter
    activities = Counter(
        v["activity"] for v in labels.values() if not v.get("interpolated")
    )
    if activities:
        dist = ", ".join(f"{k}={v}" for k, v in activities.most_common())
        log.info(f"Activity label distribution (direct frames): {dist}")


def _get_gemini_model():
    """Get a configured Gemini generative model instance."""
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(config.GEMINI_MODEL)
