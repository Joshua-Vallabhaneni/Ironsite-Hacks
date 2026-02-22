"""
video_io.py — MP4 loading, frame extraction, clip cutting.
Skip-on-decode-error: never crash the pipeline on a single bad file.
"""
import os
import cv2
import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple, Generator

from . import config

log = logging.getLogger(__name__)


def list_videos(input_dir: str) -> List[str]:
    """Return sorted list of .mp4 files in directory."""
    vids = sorted([
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith(".mp4")
    ])
    log.info(f"Found {len(vids)} video files in {input_dir}")
    return vids


def get_video_info(video_path: str) -> Optional[dict]:
    """Get basic video metadata. Returns None if file cannot be opened."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.warning(f"Cannot open video: {video_path}")
            return None
        info = {
            "path": video_path,
            "filename": os.path.basename(video_path),
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        }
        info["duration_sec"] = info["frame_count"] / max(info["fps"], 1.0)
        cap.release()
        return info
    except Exception as e:
        log.warning(f"Error reading video info for {video_path}: {e}")
        return None


def extract_frame_at_time(video_path: str, timestamp_sec: float) -> Optional[np.ndarray]:
    """Extract a single frame at a given timestamp."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000.0)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        return frame
    except Exception as e:
        log.warning(f"Error extracting frame at {timestamp_sec}s from {video_path}: {e}")
        return None


def iterate_frames(video_path: str, sample_every_sec: float = None,
                   max_minutes: float = None) -> Generator[Tuple[float, np.ndarray], None, None]:
    """
    Yield (timestamp_sec, frame) pairs from video.
    If sample_every_sec is None, yields every frame.
    Skips decode errors silently.
    """
    if sample_every_sec is None:
        sample_every_sec = 1.0 / 30.0  # every frame at ~30fps

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.warning(f"Cannot open video: {video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        max_sec = max_minutes * 60.0 if max_minutes else float("inf")
        next_sample_sec = 0.0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if current_sec > max_sec:
                break

            if current_sec >= next_sample_sec:
                yield (current_sec, frame)
                next_sample_sec = current_sec + sample_every_sec

        cap.release()
    except Exception as e:
        log.warning(f"Error iterating frames in {video_path}: {e}")


def iterate_all_frames(video_path: str, max_minutes: float = None) -> Generator[Tuple[int, float, np.ndarray], None, None]:
    """
    Yield (frame_index, timestamp_sec, frame) for EVERY frame (needed for motion computation).
    Skips decode errors silently.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.warning(f"Cannot open video: {video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        max_sec = max_minutes * 60.0 if max_minutes else float("inf")
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            current_sec = idx / fps
            if current_sec > max_sec:
                break
            yield (idx, current_sec, frame)
            idx += 1

        cap.release()
    except Exception as e:
        log.warning(f"Error iterating all frames in {video_path}: {e}")


def save_frame(frame: np.ndarray, output_path: str,
               size: Tuple[int, int] = None) -> str:
    """Save frame to disk, optionally resizing. Returns the path."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if size:
        frame = cv2.resize(frame, size)
    cv2.imwrite(output_path, frame)
    return output_path


def save_crop(frame: np.ndarray, bbox_norm: List[float], output_path: str,
              padding: float = None) -> Optional[str]:
    """
    Crop frame using normalized [x,y,w,h] bbox and save.
    Returns path or None on failure.
    """
    if bbox_norm is None or len(bbox_norm) != 4:
        return None
    if padding is None:
        padding = config.CROP_PADDING

    h, w = frame.shape[:2]
    x, y, bw, bh = bbox_norm

    # Add padding
    x1 = max(0, int((x - padding) * w))
    y1 = max(0, int((y - padding) * h))
    x2 = min(w, int((x + bw + padding) * w))
    y2 = min(h, int((y + bh + padding) * h))

    if x2 <= x1 or y2 <= y1:
        return None

    crop = frame[y1:y2, x1:x2]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, crop)
    return output_path


def _draw_region_overlay(frame: np.ndarray, region: int) -> np.ndarray:
    """
    Draw a 3×3 grid overlay on a frame, highlighting the given region cell
    with a semi-transparent orange fill and solid border.
    Grid lines are drawn faintly so the manager can see all nine zones.
    """
    h, w = frame.shape[:2]
    cell_w, cell_h = w // 3, h // 3
    col, row = region % 3, region // 3
    x0, y0 = col * cell_w, row * cell_h
    x1, y1 = x0 + cell_w, y0 + cell_h

    # Semi-transparent orange fill on the active region
    overlay = frame.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 140, 255), cv2.FILLED)
    frame = cv2.addWeighted(overlay, 0.35, frame, 0.65, 0)

    # Solid orange border on the active region
    cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 140, 255), 3)

    # Faint white grid lines for context
    for i in range(1, 3):
        cv2.line(frame, (i * cell_w, 0), (i * cell_w, h), (200, 200, 200), 1)
        cv2.line(frame, (0, i * cell_h), (w, i * cell_h), (200, 200, 200), 1)

    return frame


def cut_clip(video_path: str, center_sec: float, output_path: str,
             window_sec: float = None,
             overlay_region: Optional[int] = None) -> Optional[str]:
    """
    Cut a short clip from video centered on center_sec, ±window_sec.
    If overlay_region is set (0-8), draws a 3×3 grid with that cell highlighted
    on every frame so the manager can see which area of the frame is relevant.
    Returns output path or None on failure.
    """
    if window_sec is None:
        window_sec = config.EVENT_WINDOW_SEC

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        start_sec = max(0, center_sec - window_sec)
        end_sec = center_sec + window_sec

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out_fps = min(fps, config.CLIP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer = cv2.VideoWriter(output_path, fourcc, out_fps, (width, height))

        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000.0)
        frames_written = 0
        max_frames = int((end_sec - start_sec) * fps) + 10  # safety margin

        while frames_written < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            current_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if current_sec > end_sec:
                break
            if overlay_region is not None:
                frame = _draw_region_overlay(frame, overlay_region)
            writer.write(frame)
            frames_written += 1

        writer.release()
        cap.release()

        if frames_written == 0:
            os.remove(output_path)
            return None

        return output_path
    except Exception as e:
        log.warning(f"Error cutting clip from {video_path}: {e}")
        return None


def format_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
