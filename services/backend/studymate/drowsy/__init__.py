"""Webcam drowsiness detection (opt-in, SPEC 7.3).

camera.py (capture thread) -> face.py (EAR, head pitch) -> detector.py (PERCLOS, pitch drops,
states) wired by session.py; trace.py / replay.py / synth.py are numeric-only tuning tools.
Frames never leave memory; only numbers are kept.
"""
