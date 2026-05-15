"""Face detection.

Mediapipe 0.10.35 (the current PyPI release) dropped the ``mp.solutions``
top-level namespace; the new ``mediapipe.tasks`` API requires a
downloadable ``.tflite`` model bundle which is not zero-cost-friendly.

For the POC we therefore use OpenCV's bundled Haar cascade
(``haarcascade_frontalface_default.xml``), which ships with the
``opencv-python`` wheel and so requires no extra download. This is
documented in DECISIONS.md D-010. Production may switch to RetinaFace
(open weights, ~100 MB) once we have a stable storage plan.

The fraction of generated images with ``has_face == False`` is itself a
reported diagnostic (proposal §6.2 step 2) and is preserved here.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

_MIN_FACE_AREA_PX = 100  # 10×10 — anything smaller is noise on 512px outputs
_CASCADE_FILE = "haarcascade_frontalface_default.xml"

# Lazy-loaded singleton — Haar XML files load in <50 ms but we still amortise.
_cascade: cv2.CascadeClassifier | None = None


def _ascii_cascade_path() -> str:
    """Return an ASCII-only filesystem path to the Haar XML.

    The cv2 C++ side cannot open files when the path contains non-ASCII
    characters on Windows (e.g. the ``ó`` in our project root). We copy
    the bundled cascade to the user's temp dir, which is guaranteed ASCII,
    on first call and cache the location.
    """
    bundled = Path(cv2.data.haarcascades) / _CASCADE_FILE
    cached_dir = Path(tempfile.gettempdir()) / "apd_haar_cache"
    cached_dir.mkdir(parents=True, exist_ok=True)
    cached = cached_dir / _CASCADE_FILE
    if not cached.exists() or cached.stat().st_size != bundled.stat().st_size:
        shutil.copy(bundled, cached)
    return str(cached)


def _get_cascade() -> cv2.CascadeClassifier:
    global _cascade
    if _cascade is None:
        path = _ascii_cascade_path()
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            raise RuntimeError(f"failed to load Haar cascade from {path!r}")
        _cascade = cascade
    return _cascade


@dataclass(frozen=True)
class FaceResult:
    has_face: bool
    n_faces: int
    bbox: tuple[int, int, int, int] | None  # (x, y, w, h) on the source image
    cropped_bgr: np.ndarray | None  # cropped face patch in BGR, or None


def _read_image_unicode_safe(image_path: Path) -> np.ndarray | None:
    """Read ``image_path`` into a BGR ndarray, tolerating non-ASCII paths.

    OpenCV's ``cv2.imread`` cannot open paths containing non-ASCII characters
    on Windows because it uses ``fopen()`` with the system code page. We
    sidestep that by reading the bytes with Python's I/O (which is
    fully Unicode-aware) and decoding through ``cv2.imdecode``.
    """
    try:
        with open(image_path, "rb") as fh:
            buf = fh.read()
    except OSError:
        return None
    if not buf:
        return None
    array = np.frombuffer(buf, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def detect_face(image_path: Path) -> FaceResult:
    """Detect a face in ``image_path`` and return the largest detection.

    Returns ``FaceResult(False, 0, None, None)`` if the image cannot be read
    or no face passes the minimum-area filter.
    """
    bgr = _read_image_unicode_safe(image_path)
    if bgr is None:
        return FaceResult(False, 0, None, None)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    cascade = _get_cascade()
    detections = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(30, 30),
    )
    if len(detections) == 0:
        return FaceResult(False, 0, None, None)

    best_idx = int(np.argmax([w * h for (_, _, w, h) in detections]))
    x, y, w, h = (int(v) for v in detections[best_idx])
    area = w * h
    if area < _MIN_FACE_AREA_PX:
        return FaceResult(False, len(detections), None, None)

    return FaceResult(
        has_face=True,
        n_faces=int(len(detections)),
        bbox=(x, y, w, h),
        cropped_bgr=bgr[y : y + h, x : x + w].copy(),
    )
