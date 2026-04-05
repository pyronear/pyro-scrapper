"""Wildfire detection inference utilities.

This module groups the shared helpers used by the annotation pipeline:
- camera metadata parsing from filenames
- timestamp parsing
- leaf-folder discovery for scraped images
- box conversion utilities used before sending annotation payloads

"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

TIMESTAMP_FMT = "%Y%m%d_%H%M%S"


@dataclass
class ImageEntry:
    """Container for image path and timestamp."""

    path: Path
    ts: datetime


def parse_metadata_from_filename(name: str) -> Optional[Tuple[str, Optional[str], float, float, str]]:
    """Extract camera ID, camera name, coordinates, and timestamp from a pipeline filename.

    Expected format:
    <cam_id>_<YYYYMMDD>_<HHMMSS>_<microseconds>_<lat>_<lon>_<cam_name>.jpg
    """
    base = os.path.basename(name)
    try:
        stem, _ = os.path.splitext(base)
        parts = stem.split("_")
        if len(parts) < 7:
            return None
        cam_id = parts[0]
        lat = float(parts[4])
        lon = float(parts[5])
        cam_name = "_".join(parts[6:]).strip()
        timestamp_str = f"{parts[1]}_{parts[2]}"
        return cam_id, cam_name or None, lat, lon, timestamp_str
    except (ValueError, TypeError):
        return None


def find_folder_metadata(folder: Path) -> Optional[Tuple[str, Optional[str], float, float]]:
    """Return the first camera metadata tuple found in a folder.

    Output: (cam_id, cam_name, lat, lon) or None if no valid filename is found.
    """
    for image_path in folder.glob("*.jpg"):
        parsed = parse_metadata_from_filename(image_path.name)
        if parsed is None:
            continue
        cam_id, cam_name, lat, lon, _ = parsed
        return cam_id, cam_name, lat, lon
    return None


def parse_timestamp_from_filename(name: str) -> Optional[datetime]:
    """Extract timestamp from filename based on the pipeline pattern."""
    parsed = parse_metadata_from_filename(name)
    if parsed is None:
        return None
    _, _, _, _, ts_str = parsed
    try:
        return datetime.strptime(ts_str, TIMESTAMP_FMT)
    except ValueError:
        return None


def xyxy_to_yolo(x1: float, y1: float, x2: float, y2: float) -> Optional[Tuple[float, float, float, float]]:
    """Convert normalized xyxy coordinates to YOLO cx, cy, w, h.

    The input box is expected to be normalized in [0, 1]. The output is the
    equivalent YOLO representation with center coordinates and size.
    """
    if x2 <= x1 or y2 <= y1:
        return None
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    w = x2 - x1
    h = y2 - y1
    return cx, cy, w, h


def iter_leaf_folders(root: Path) -> Iterable[Path]:
    """Yield leaf folders under `root` that contain images."""
    if not root.exists():
        return []
    for cam_dir in root.iterdir():
        if not cam_dir.is_dir():
            continue
        for az_dir in cam_dir.iterdir():
            if not az_dir.is_dir():
                continue
            yield az_dir


def scan_folder_images(folder: Path) -> List[ImageEntry]:
    """Scan a folder and return image entries sorted by timestamp."""
    entries: List[ImageEntry] = []
    for p in sorted(folder.glob("*.jpg")):
        ts = parse_timestamp_from_filename(p.name)
        if ts is None:
            continue
        entries.append(ImageEntry(p, ts))
    entries.sort(key=lambda e: e.ts)
    return entries
