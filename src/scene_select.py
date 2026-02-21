"""
scene_select.py — Component 1: Agentic frame selection.
Uniform + motion-biased + histogram scene transitions.
No CLIP, no embeddings.
"""
import cv2
import logging
import numpy as np
from typing import List, Tuple, Optional

from . import config
from .video_io import format_timestamp

log = logging.getLogger(__name__)


def compute_motion_magnitude(prev_gray: np.ndarray, curr_gray: np.ndarray) -> float:
    """
    Motion magnitude = mean absolute pixel difference between
    consecutive grayscale frames after resizing to 224×224.
    """
    size = (224, 224)
    p = cv2.resize(prev_gray, size)
    c = cv2.resize(curr_gray, size)
    diff = np.abs(p.astype(np.float32) - c.astype(np.float32))
    return float(np.mean(diff))


def compute_hist_diff(prev_frame: np.ndarray, curr_frame: np.ndarray) -> float:
    """
    Scene transition via H-channel histogram chi-square distance.
    Convert to HSV, compute 32-bin H histogram, chi-square compare.
    """
    prev_hsv = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2HSV)
    curr_hsv = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2HSV)

    hist_prev = cv2.calcHist([prev_hsv], [0], None, [32], [0, 180])
    hist_curr = cv2.calcHist([curr_hsv], [0], None, [32], [0, 180])

    cv2.normalize(hist_prev, hist_prev)
    cv2.normalize(hist_curr, hist_curr)

    return cv2.compareHist(hist_prev, hist_curr, cv2.HISTCMP_CHISQR)


def select_frames(video_path: str, video_info: dict,
                  sample_every_sec: float = None,
                  max_minutes: float = None) -> Tuple[List[dict], List[dict]]:
    """
    Select keyframes from a video using three methods:
    1. Uniform sampling every sample_every_sec
    2. Motion-biased: oversample high-motion frames
    3. Scene transitions: histogram diff peaks

    Returns:
        keyframes: list of keyframe metadata dicts
        candidate_windows: list of event-window candidates (±4s)
    """
    if sample_every_sec is None:
        sample_every_sec = config.SAMPLE_EVERY_SEC

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log.warning(f"Cannot open video for scene selection: {video_path}")
        return [], []

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    max_sec = max_minutes * 60.0 if max_minutes else float("inf")
    filename = video_info["filename"]

    keyframes = []
    candidate_windows = []
    selected_times = set()

    # We'll scan at a moderate rate for motion/transition analysis
    # and pick uniform samples along the way
    analysis_interval = max(1, int(fps * 0.5))  # analyze every 0.5s

    prev_frame = None
    prev_gray = None
    frame_idx = 0
    next_uniform_sec = 0.0

    # Rolling stats for motion
    motion_values = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_sec = frame_idx / fps
        if current_sec > max_sec:
            break

        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Only analyze at intervals for efficiency
        if frame_idx % analysis_interval == 0 and prev_frame is not None:
            motion_mag = compute_motion_magnitude(prev_gray, curr_gray)
            hist_diff = compute_hist_diff(prev_frame, frame)
            motion_values.append(motion_mag)

            # --- Uniform sampling ---
            if current_sec >= next_uniform_sec:
                fid = f"{filename}_{current_sec:.1f}s"
                keyframes.append({
                    "frame_id": fid,
                    "video_file": filename,
                    "timestamp_sec": round(current_sec, 2),
                    "timestamp_fmt": format_timestamp(current_sec),
                    "reason": "uniform",
                    "motion_magnitude": round(motion_mag, 2),
                    "hist_diff": round(hist_diff, 4),
                    "frame_index": frame_idx,
                })
                selected_times.add(round(current_sec, 1))
                next_uniform_sec = current_sec + sample_every_sec

            # --- Motion-biased oversampling ---
            if motion_mag > config.MOTION_THRESH_HIGH:
                t_key = round(current_sec, 1)
                if t_key not in selected_times:
                    fid = f"{filename}_{current_sec:.1f}s"
                    keyframes.append({
                        "frame_id": fid,
                        "video_file": filename,
                        "timestamp_sec": round(current_sec, 2),
                        "timestamp_fmt": format_timestamp(current_sec),
                        "reason": "motion_peak",
                        "motion_magnitude": round(motion_mag, 2),
                        "hist_diff": round(hist_diff, 4),
                        "frame_index": frame_idx,
                    })
                    selected_times.add(t_key)

                # Flag as event candidate
                candidate_windows.append({
                    "video_file": filename,
                    "center_sec": round(current_sec, 2),
                    "start_sec": round(max(0, current_sec - config.EVENT_WINDOW_SEC), 2),
                    "end_sec": round(current_sec + config.EVENT_WINDOW_SEC, 2),
                    "trigger": "motion_peak",
                    "motion_magnitude": round(motion_mag, 2),
                })

            # --- Scene transition detection ---
            if hist_diff > config.HIST_DIFF_THRESH:
                t_key = round(current_sec, 1)
                if t_key not in selected_times:
                    fid = f"{filename}_{current_sec:.1f}s"
                    keyframes.append({
                        "frame_id": fid,
                        "video_file": filename,
                        "timestamp_sec": round(current_sec, 2),
                        "timestamp_fmt": format_timestamp(current_sec),
                        "reason": "transition_candidate",
                        "motion_magnitude": round(motion_mag, 2),
                        "hist_diff": round(hist_diff, 4),
                        "frame_index": frame_idx,
                    })
                    selected_times.add(t_key)

                candidate_windows.append({
                    "video_file": filename,
                    "center_sec": round(current_sec, 2),
                    "start_sec": round(max(0, current_sec - config.EVENT_WINDOW_SEC), 2),
                    "end_sec": round(current_sec + config.EVENT_WINDOW_SEC, 2),
                    "trigger": "transition",
                    "hist_diff": round(hist_diff, 4),
                })

        prev_frame = frame.copy()
        prev_gray = curr_gray.copy()
        frame_idx += 1

    cap.release()

    # Sort by timestamp
    keyframes.sort(key=lambda x: x["timestamp_sec"])

    log.info(f"Selected {len(keyframes)} keyframes from {filename} "
             f"({len(candidate_windows)} event candidates)")

    return keyframes, candidate_windows


def uniform_sample_timestamps(video_info: dict, num_frames: int) -> List[float]:
    """
    Return evenly spaced timestamps for baseline mode.
    """
    duration = video_info.get("duration_sec", 0)
    if duration <= 0 or num_frames <= 0:
        return []
    if num_frames == 1:
        return [duration / 2.0]
    interval = duration / num_frames
    return [round(i * interval, 2) for i in range(num_frames)]
