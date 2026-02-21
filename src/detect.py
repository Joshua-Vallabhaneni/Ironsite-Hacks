"""
detect.py — MediaPipe Hands + YOLOv8 detection.
Graceful None fallbacks — never crash on missing detections.
"""
import cv2
import logging
import numpy as np
from typing import Optional, List, Tuple

from . import config

log = logging.getLogger(__name__)

# Module-level caches
_mp_hands = None
_yolo_model = None


def _load_mediapipe():
    """Load MediaPipe Hands once."""
    global _mp_hands
    if _mp_hands is not None:
        return

    try:
        import mediapipe as mp
        _mp_hands = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=2,
            min_detection_confidence=0.3,  # low threshold; we filter by our own config
        )
        log.info("MediaPipe Hands loaded")
    except Exception as e:
        log.warning(f"Failed to load MediaPipe Hands: {e}")
        _mp_hands = None


def _load_yolo():
    """Load YOLOv8 model once."""
    global _yolo_model
    if _yolo_model is not None:
        return

    try:
        from ultralytics import YOLO
        _yolo_model = YOLO(config.YOLO_MODEL)
        log.info(f"YOLOv8 loaded: {config.YOLO_MODEL}")
    except Exception as e:
        log.warning(f"Failed to load YOLOv8: {e}")
        _yolo_model = None


def detect_hands(frame: np.ndarray) -> dict:
    """
    Detect hands using MediaPipe.

    Returns dict with:
        hand_present: bool | None (None = uncertain)
        hand_confidence: float
        hand_bbox: [x,y,w,h] normalized | None
        num_hands: int
    """
    _load_mediapipe()

    result = {
        "hand_present": None,
        "hand_confidence": 0.0,
        "hand_bbox": None,
        "num_hands": 0,
    }

    if _mp_hands is None:
        return result

    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_result = _mp_hands.process(rgb)

        if mp_result.multi_hand_landmarks:
            best_conf = 0.0
            best_bbox = None

            for idx, hand_landmarks in enumerate(mp_result.multi_hand_landmarks):
                # Get confidence from handedness
                conf = 0.5  # default
                if mp_result.multi_handedness and idx < len(mp_result.multi_handedness):
                    conf = mp_result.multi_handedness[idx].classification[0].score

                # Compute bbox from landmarks
                xs = [lm.x for lm in hand_landmarks.landmark]
                ys = [lm.y for lm in hand_landmarks.landmark]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)
                bbox = [x_min, y_min, x_max - x_min, y_max - y_min]

                if conf > best_conf:
                    best_conf = conf
                    best_bbox = bbox

            result["num_hands"] = len(mp_result.multi_hand_landmarks)
            result["hand_confidence"] = round(best_conf, 3)
            result["hand_bbox"] = [round(v, 4) for v in best_bbox] if best_bbox else None

            if best_conf >= config.HAND_CONF_THRESH:
                result["hand_present"] = True
            else:
                result["hand_present"] = None  # uncertain
        else:
            result["hand_present"] = False
            result["hand_confidence"] = 0.0

    except Exception as e:
        log.debug(f"MediaPipe detection error: {e}")
        result["hand_present"] = None

    return result


def detect_objects(frame: np.ndarray) -> dict:
    """
    Detect objects using YOLOv8.

    Returns dict with:
        tool_present: bool
        tool_class: str | None
        tool_bbox: [x,y,w,h] normalized | None
        tool_confidence: float
        person_present: bool
        person_bbox: [x,y,w,h] normalized | None
        all_detections: list of {class, bbox, confidence}
    """
    _load_yolo()

    result = {
        "tool_present": False,
        "tool_class": None,
        "tool_bbox": None,
        "tool_confidence": 0.0,
        "person_present": False,
        "person_bbox": None,
        "all_detections": [],
    }

    if _yolo_model is None:
        return result

    try:
        results = _yolo_model(frame, conf=config.YOLO_CONF_THRESH, verbose=False)

        if not results or len(results) == 0:
            return result

        h, w = frame.shape[:2]
        detections = results[0]

        # Tool-like COCO classes (relevant to construction)
        tool_classes = {
            "scissors", "knife", "hammer", "screwdriver",
            "wrench", "toothbrush",  # proxy for small tool
            "cell phone",  # level/phone
            "bottle",  # spray/container
        }
        # Material classes
        material_classes = {
            "backpack", "suitcase", "handbag",  # toolbox proxies
            "box", "bucket",
        }

        best_tool = None
        best_tool_conf = 0.0

        for box in detections.boxes:
            cls_id = int(box.cls[0])
            cls_name = detections.names[cls_id]
            conf = float(box.conf[0])

            # Normalize bbox to [x,y,w,h] in [0,1]
            xyxy = box.xyxy[0].cpu().numpy()
            bbox_norm = [
                round(float(xyxy[0]) / w, 4),
                round(float(xyxy[1]) / h, 4),
                round(float(xyxy[2] - xyxy[0]) / w, 4),
                round(float(xyxy[3] - xyxy[1]) / h, 4),
            ]

            det = {
                "class": cls_name,
                "bbox": bbox_norm,
                "confidence": round(conf, 3),
            }
            result["all_detections"].append(det)

            # Check person
            if cls_name == "person" and conf > 0.3:
                result["person_present"] = True
                result["person_bbox"] = bbox_norm

            # Check tools
            if cls_name in tool_classes and conf > best_tool_conf:
                best_tool = det
                best_tool_conf = conf

            # Also check material classes as tools
            if cls_name in material_classes and conf > best_tool_conf:
                best_tool = det
                best_tool_conf = conf

        if best_tool:
            result["tool_present"] = True
            result["tool_class"] = best_tool["class"]
            result["tool_bbox"] = best_tool["bbox"]
            result["tool_confidence"] = best_tool["confidence"]

    except Exception as e:
        log.debug(f"YOLOv8 detection error: {e}")

    return result


def compute_iou(bbox1: Optional[List[float]], bbox2: Optional[List[float]]) -> float:
    """Compute IOU between two [x,y,w,h] normalized bboxes. Returns 0 if either is None."""
    if bbox1 is None or bbox2 is None:
        return 0.0

    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2

    xa = max(x1, x2)
    ya = max(y1, y2)
    xb = min(x1 + w1, x2 + w2)
    yb = min(y1 + h1, y2 + h2)

    inter = max(0, xb - xa) * max(0, yb - ya)
    area1 = w1 * h1
    area2 = w2 * h2
    union = area1 + area2 - inter

    if union <= 0:
        return 0.0
    return round(inter / union, 4)


def get_bbox_centroid(bbox: Optional[List[float]]) -> Optional[Tuple[float, float]]:
    """Get centroid of [x,y,w,h] bbox. Returns None if bbox is None."""
    if bbox is None:
        return None
    return (bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2)


def get_spatial_region(bbox: Optional[List[float]]) -> int:
    """
    Get 3×3 grid cell index (0–8) for bbox centroid.
    Returns 4 (center) if bbox is None.
    """
    centroid = get_bbox_centroid(bbox)
    if centroid is None:
        return 4  # default center

    cx, cy = centroid
    col = min(2, int(cx * 3))
    row = min(2, int(cy * 3))
    return row * 3 + col


def is_in_workface(bbox: Optional[List[float]]) -> bool:
    """
    Check if bbox centroid is in lower-center third of frame.
    Returns False if bbox is None.
    """
    centroid = get_bbox_centroid(bbox)
    if centroid is None:
        return False

    cx, cy = centroid
    # Lower third: y > 0.67, Center third: 0.33 < x < 0.67
    return cy > 0.67 and 0.33 < cx < 0.67
