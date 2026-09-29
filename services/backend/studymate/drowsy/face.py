"""Face metrics from MediaPipe FaceLandmarker: eye aspect ratio (EAR) and head pitch.

Privacy: `FaceAnalyzer.analyze` turns one frame into three numbers. The RGB copy and the
MediaPipe image are locals that die when the call returns; nothing is cached or logged.

EAR (SPEC 7.3) per eye, with p1..p6 ordered as in Soukupova & Cech (2016):

    EAR = (|p2 - p6| + |p3 - p5|) / (2 |p1 - p4|)

p1/p4 are the horizontal eye corners, p2/p3 points on the upper lid and p6/p5 the lower-lid
points directly below them. MediaPipe Face Mesh indices (468-point topology; the 478-point
FaceLandmarker output keeps the same first 468 points):

    subject's right eye: p1=33 (outer)  p2=160 p3=158  p4=133 (inner) p5=153 p6=144
    subject's left eye:  p1=362 (inner) p2=385 p3=387  p4=263 (outer) p5=373 p6=380

Distances are measured in pixels (normalised x/y scaled by width/height) so the ratio does not
depend on the frame's aspect ratio. The reported EAR is the mean of both eyes.

Head pitch comes from the facial transformation matrix (canonical face -> camera metric
space). That space is right-handed with +y up and the camera looking down -z, and the
canonical face looks along +z (towards the camera). The face's forward axis is the third
rotation column f; pitch = asin(-f_y) in degrees, so positive = looking down, independent of
yaw. The sign was checked on a still portrait: a perspective warp that brings the top of
the face closer to the camera (head tilted forward) raised the pitch, and a clockwise in-plane
rotation produced R[1,0] < 0 (y-up convention).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

RIGHT_EYE: tuple[int, int, int, int, int, int] = (33, 160, 158, 133, 153, 144)
LEFT_EYE: tuple[int, int, int, int, int, int] = (362, 385, 387, 263, 373, 380)
_EYE_INDICES = RIGHT_EYE + LEFT_EYE


@dataclass(frozen=True, slots=True)
class FaceMetrics:
    face: bool
    ear: float | None = None
    pitch: float | None = None  # degrees, positive = looking down


def eye_aspect_ratio(points: Sequence[Sequence[float]] | np.ndarray) -> float | None:
    """EAR of one eye from six (x, y) points ordered p1..p6. None if degenerate."""
    p = np.asarray(points, dtype=np.float64)
    if p.shape != (6, 2):
        raise ValueError("expected six 2D points")
    width = float(np.linalg.norm(p[0] - p[3]))
    if width < 1e-6:
        return None
    vertical = float(np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4]))
    return vertical / (2.0 * width)


def mean_ear(points_by_index: dict[int, tuple[float, float]]) -> float | None:
    """Mean EAR of both eyes from pixel coordinates keyed by Face Mesh index."""
    values = []
    for eye in (RIGHT_EYE, LEFT_EYE):
        ear = eye_aspect_ratio([points_by_index[i] for i in eye])
        if ear is not None:
            values.append(ear)
    return sum(values) / len(values) if values else None


def ear_from_landmarks(landmarks: Sequence[Any], width: int, height: int) -> float | None:
    """Mean EAR from normalised MediaPipe landmarks (objects with .x/.y in 0..1)."""
    if len(landmarks) <= max(_EYE_INDICES):
        return None
    pts = {i: (float(landmarks[i].x) * width, float(landmarks[i].y) * height) for i in _EYE_INDICES}
    return mean_ear(pts)


def pitch_from_matrix(matrix: Any) -> float | None:
    """Head pitch in degrees (positive = looking down) from a 4x4 facial transformation matrix."""
    m = np.asarray(matrix, dtype=np.float64)
    if m.shape[0] < 3 or m.shape[1] < 3:
        return None
    forward = m[:3, 2]
    norm = float(np.linalg.norm(forward))
    if not math.isfinite(norm) or norm < 1e-9:
        return None
    return math.degrees(math.asin(max(-1.0, min(1.0, -forward[1] / norm))))


class FaceAnalyzer:
    """MediaPipe FaceLandmarker in VIDEO mode. Use from one thread at a time; call close()."""

    def __init__(self, model_path: Path, min_confidence: float = 0.5) -> None:
        from mediapipe.tasks.python import BaseOptions, vision

        # Load from a buffer so a non-ASCII install path never reaches the native file loader.
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=model_path.read_bytes()),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=min_confidence,
            min_face_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker: Any = vision.FaceLandmarker.create_from_options(options)
        self._last_ts = -1

    def analyze(self, frame_bgr: np.ndarray, t: float) -> FaceMetrics:
        """Metrics for one BGR frame captured at monotonic time `t` (seconds)."""
        import cv2
        import mediapipe as mp

        # VIDEO mode needs strictly increasing timestamps.
        ts = max(int(t * 1000.0), self._last_ts + 1)
        self._last_ts = ts
        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, ts)
        del image, rgb
        if not result.face_landmarks:
            return FaceMetrics(face=False)
        ear = ear_from_landmarks(result.face_landmarks[0], width, height)
        matrices = result.facial_transformation_matrixes
        pitch = pitch_from_matrix(matrices[0]) if matrices else None
        return FaceMetrics(face=True, ear=ear, pitch=pitch)

    def close(self) -> None:
        landmarker, self._landmarker = self._landmarker, None
        if landmarker is not None:
            landmarker.close()
