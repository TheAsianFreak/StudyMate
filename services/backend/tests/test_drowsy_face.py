"""EAR and head-pitch math on hand-made landmarks; FaceLandmarker smoke test on a blank frame."""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

from studymate.drowsy.face import (
    LEFT_EYE,
    RIGHT_EYE,
    FaceAnalyzer,
    ear_from_landmarks,
    eye_aspect_ratio,
    mean_ear,
    pitch_from_matrix,
)


def eye(cx: float, cy: float, width: float, opening: float) -> list[tuple[float, float]]:
    """p1..p6 of an eye: corners at +-width/2, lids at +-opening/2 (image y grows down)."""
    w, o = width / 2, opening / 2
    return [
        (cx - w, cy),  # p1 corner
        (cx - w / 3, cy - o),  # p2 upper
        (cx + w / 3, cy - o),  # p3 upper
        (cx + w, cy),  # p4 corner
        (cx + w / 3, cy + o),  # p5 lower (below p3)
        (cx - w / 3, cy + o),  # p6 lower (below p2)
    ]


def test_eye_aspect_ratio_formula() -> None:
    # (|p2-p6| + |p3-p5|) / (2|p1-p4|) = (4 + 4) / (2 * 10)
    assert eye_aspect_ratio(eye(0, 0, 10, 4)) == pytest.approx(0.4)
    assert eye_aspect_ratio(eye(50, 20, 30, 0)) == pytest.approx(0.0)
    assert eye_aspect_ratio([(1, 1)] * 6) is None
    with pytest.raises(ValueError):
        eye_aspect_ratio([(0, 0)] * 5)


def test_mean_ear_of_both_eyes() -> None:
    pts: dict[int, tuple[float, float]] = {}
    pts.update(zip(RIGHT_EYE, eye(100, 100, 30, 9), strict=True))  # 0.30
    pts.update(zip(LEFT_EYE, eye(200, 100, 30, 6), strict=True))  # 0.20
    assert mean_ear(pts) == pytest.approx(0.25)


def test_ear_from_normalised_landmarks_uses_pixel_aspect() -> None:
    width, height = 640, 480
    marks = [SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(478)]
    for indices, cx in ((RIGHT_EYE, 250.0), (LEFT_EYE, 390.0)):
        for i, (x, y) in zip(indices, eye(cx, 200.0, 40.0, 12.0), strict=True):
            marks[i] = SimpleNamespace(x=x / width, y=y / height, z=0.0)
    assert ear_from_landmarks(marks, width, height) == pytest.approx(0.30)
    assert ear_from_landmarks(marks[:100], width, height) is None


def rot_x(deg: float) -> np.ndarray:
    a = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])


def rot_y(deg: float) -> np.ndarray:
    a = math.radians(deg)
    return np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])


def as_matrix(r: np.ndarray, scale: float = 1.0) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3] = r * scale
    m[:3, 3] = (0.5, 6.0, -42.0)  # face ~42 cm in front of the camera (-z)
    return m


def test_pitch_from_transformation_matrix() -> None:
    assert pitch_from_matrix(np.eye(4)) == pytest.approx(0.0)
    # Face forward axis (canonical +z) tilted towards -y (camera y is up) = looking down.
    assert pitch_from_matrix(as_matrix(rot_x(20))) == pytest.approx(20.0)
    assert pitch_from_matrix(as_matrix(rot_x(-15))) == pytest.approx(-15.0)
    # Independent of yaw and of any uniform scale in the matrix.
    assert pitch_from_matrix(as_matrix(rot_y(60) @ rot_x(20), scale=1.3)) == pytest.approx(20.0)
    assert pitch_from_matrix(np.zeros((4, 4))) is None


def test_real_landmarker_on_blank_frame() -> None:
    from studymate.services import get_services

    registry = get_services().registry
    if not registry.installed("face-landmarker"):
        pytest.skip("face-landmarker model not installed")
    analyzer = FaceAnalyzer(registry.path("face-landmarker"))
    try:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        first = analyzer.analyze(blank, 1.0)
        second = analyzer.analyze(blank, 1.0)  # same timestamp is bumped, not rejected
        assert first.face is False and first.ear is None and first.pitch is None
        assert second.face is False
    finally:
        analyzer.close()
    analyzer.close()  # idempotent
