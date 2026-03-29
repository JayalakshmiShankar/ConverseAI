import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
from flask import Blueprint, request


mouth_bp = Blueprint("mouth_detection", __name__)


@dataclass
class MouthResult:
    mouth: str
    confidence: float


class MouthDetector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mp = None
        self._face_mesh = None

    def _ensure(self) -> bool:
        if self._face_mesh is not None:
            return True
        with self._lock:
            if self._face_mesh is not None:
                return True
            try:
                import mediapipe as mp  # type: ignore
            except Exception:
                return False
            self._mp = mp
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            return True

    def analyze_bgr(self, image_bgr: np.ndarray) -> MouthResult:
        ok = self._ensure()
        if not ok or self._face_mesh is None:
            return MouthResult(mouth="not_available", confidence=0.0)

        h, w = image_bgr.shape[:2]
        if h < 2 or w < 2:
            return MouthResult(mouth="not_visible", confidence=0.0)

        image_rgb = image_bgr[:, :, ::-1]
        res = self._face_mesh.process(image_rgb)
        if not res.multi_face_landmarks:
            return MouthResult(mouth="not_visible", confidence=0.0)

        lm = res.multi_face_landmarks[0].landmark

        upper = lm[13]
        lower = lm[14]
        left = lm[61]
        right = lm[291]

        open_dist = float(((upper.x - lower.x) ** 2 + (upper.y - lower.y) ** 2) ** 0.5)
        width_dist = float(((left.x - right.x) ** 2 + (left.y - right.y) ** 2) ** 0.5)

        ratio = open_dist / max(width_dist, 1e-6)
        threshold = 0.035

        if ratio > threshold:
            conf = min(1.0, max(0.0, (ratio - threshold) / 0.08))
            return MouthResult(mouth="open", confidence=round(conf, 3))

        conf = min(1.0, max(0.0, 1.0 - (ratio / threshold)))
        return MouthResult(mouth="closed", confidence=round(conf, 3))


_detector = MouthDetector()


def _decode_frame(frame_bytes: bytes) -> np.ndarray | None:
    try:
        import cv2  # type: ignore
    except Exception:
        return None

    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return img


@mouth_bp.post("/mouth-status")
def mouth_status() -> tuple[dict[str, Any], int]:
    f = request.files.get("frame")
    if not f:
        return {"mouth": "not_visible", "confidence": 0.0}, 200

    raw = f.read()
    if not raw:
        return {"mouth": "not_visible", "confidence": 0.0}, 200

    img = _decode_frame(raw)
    if img is None:
        return {"mouth": "not_available", "confidence": 0.0}, 200

    r = _detector.analyze_bgr(img)
    return {"mouth": r.mouth, "confidence": r.confidence}, 200

