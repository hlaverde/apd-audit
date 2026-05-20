"""CASCo PERLA classifier wrapper.

Wraps the maintained reference implementation of CASCo (Rejón Piña & Ma
2023, *Social Science Quarterly*) distributed as ``skin-tone-classifier``
on PyPI. The library is the third leg of the 2-of-3 phenotype concordance
rule prescribed by the proposal §6.2.

Two defensive patches sit at the top of this module because CASCo (and
OpenCV in general) breaks on Windows when the project path contains
non-ASCII characters such as the *ó* in *Investigación*:

1.  ``cv2.data.haarcascades`` is redirected to an ASCII tmp cache so the
    Haar XML cascade that ``stone`` loads at module import succeeds.
2.  Every input image is copied to a temp ASCII path before being passed
    to ``stone.process``, sidestepping the same ``cv2.imread`` bug.

CASCo returns the closest PERLA-palette anchor as a hex colour and a
letter label ("CA"–"CK"); the proposal uses the integer scale 1..11 with
1 = lightest and 11 = darkest. We map hex → integer directly from the
published anchor list (Rejón Piña & Ma 2023 §3.2 / project website).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)

# ----- One-time cv2.data redirect to ASCII path (Windows cp1252 fix) -----
_ASCII_DATA_DIR = Path(tempfile.gettempdir()) / "apd_cv2_data_cache"
_ASCII_DATA_DIR.mkdir(parents=True, exist_ok=True)
_src_dir = Path(cv2.data.haarcascades)
if _src_dir.is_dir() and _src_dir.resolve() != _ASCII_DATA_DIR.resolve():
    for _xml in _src_dir.glob("*.xml"):
        _dst = _ASCII_DATA_DIR / _xml.name
        if not _dst.exists() or _dst.stat().st_size != _xml.stat().st_size:
            try:
                shutil.copy(_xml, _dst)
            except OSError as exc:  # pragma: no cover
                logger.warning("could not cache cv2 cascade %s: %s", _xml.name, exc)
    # Use the platform separator. On Windows the previous hard-coded ``"\\"``
    # worked; on Linux (Kaggle, GH Actions) it produced an invalid path like
    # ``/tmp/apd_cv2_data_cache\\`` that crashed downstream when ``stone``
    # tried to load the cascade. ``os.sep`` resolves to ``\`` on Windows and
    # ``/`` on POSIX, matching the convention cv2 expects on each platform.
    cv2.data.haarcascades = str(_ASCII_DATA_DIR) + os.sep

# Stone must be imported *after* the patch — it loads cascades at module init.
import stone  # noqa: E402

# ----- PERLA palette hex → ordinal --------------------------------------
# The PERLA palette anchors used by CASCo are listed dark-to-light in the
# published CASCo paper (Rejón Piña & Ma 2023, table 2) and on the
# upstream project page. PERLA itself numbers tones light-to-dark (1 =
# lightest, 11 = darkest), so we invert.
_PERLA_HEX_DARK_TO_LIGHT: tuple[str, ...] = (
    "#373028",  # PERLA 11 (darkest)
    "#422811",  # PERLA 10
    "#513B2E",  # PERLA  9
    "#6F503C",  # PERLA  8
    "#81654F",  # PERLA  7
    "#9D7A54",  # PERLA  6
    "#BEA07E",  # PERLA  5
    "#E5C8A6",  # PERLA  4
    "#E7C1B8",  # PERLA  3
    "#F3DAD6",  # PERLA  2
    "#FBF2F3",  # PERLA  1 (lightest)
)
HEX_TO_PERLA: dict[str, int] = {
    h.lower(): 11 - i for i, h in enumerate(_PERLA_HEX_DARK_TO_LIGHT)
}


def compute_casco_perla(image_path: Path) -> int | None:
    """Return CASCo's PERLA tone (1..11) for ``image_path``, or None.

    Returns ``None`` when:
        * the file cannot be copied (e.g. missing),
        * CASCo finds no face,
        * CASCo's returned hex is not on the PERLA palette (defensive guard).
    """
    src = Path(image_path)
    if not src.is_file():
        return None

    with tempfile.TemporaryDirectory() as tmp:
        ascii_dst = Path(tmp) / src.name
        try:
            shutil.copy(src, ascii_dst)
        except OSError as exc:
            logger.warning("could not stage %s for CASCo: %s", src.name, exc)
            return None
        try:
            result = stone.process(
                filename_or_url=str(ascii_dst),
                image_type="color",
                tone_palette="perla",
                return_report_image=False,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("CASCo errored on %s: %s", src.name, exc)
            return None

    faces = result.get("faces") or []
    if not faces:
        return None

    # Pick the highest-accuracy face if multiple were detected.
    best = max(faces, key=lambda f: float(f.get("accuracy", 0.0)))
    hex_color = (best.get("skin_tone") or "").strip().lower()
    return HEX_TO_PERLA.get(hex_color)


def is_available() -> bool:
    """Whether the ``skin-tone-classifier`` dependency is importable."""
    try:
        import stone  # noqa: F401
    except ImportError:
        return False
    return True
