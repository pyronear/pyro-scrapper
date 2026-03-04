"""Wildfire detection inference using pyroengine.

This module handles temporal image sequence detection and fire confidence scoring
using the pyroengine model. It scans image folders, identifies sequences of
consecutive images, and runs inference on each sequence.

"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image
from pyroengine.core import Engine

TIMESTAMP_FMT = "%Y%m%d_%H%M%S"


@dataclass
class ImageEntry:
    """Container for image path and timestamp."""

    path: Path
    ts: datetime


def extract_timestamp_prefix(name: str) -> Optional[str]:
    """Return the YYYYMMDD_HHMMSS portion from the filename."""
    base = os.path.basename(name)
    try:
        _, rest = base.split("_", 1)
        stem, _ = os.path.splitext(rest)
        parts = stem.split("_")
        if len(parts) < 2:
            return None
        return "_".join(parts[:2])
    except ValueError:
        return None


def parse_timestamp_from_filename(name: str) -> Optional[datetime]:
    """Extract timestamp from filename based on pipeline pattern.

    Expected pattern: CAMID_YYYYMMDD_HHMMSS_MICRO_lat_long_name.jpg
    Returns None if it doesn't match or parses.
    """
    ts_str = extract_timestamp_prefix(name)
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, TIMESTAMP_FMT)
    except ValueError:
        return None


def parse_lat_lon_from_filename(name: str) -> tuple[Optional[float], Optional[float]]:
    """Extract latitude/longitude from filename suffix if present."""
    base = os.path.basename(name)
    try:
        _, rest = base.split("_", 1)
        stem, _ = os.path.splitext(rest)
        parts = stem.split("_")
        if len(parts) < 5:
            return None, None
        lat_raw = parts[3]
        lon_raw = parts[4]
        return float(lat_raw), float(lon_raw)
    except (ValueError, TypeError):
        return None, None


def find_folder_lat_lon(folder: Path) -> tuple[Optional[float], Optional[float]]:
    """Return the first lat/lon found in the folder's filenames."""
    for image_path in folder.glob("*.jpg"):
        lat, lon = parse_lat_lon_from_filename(image_path.name)
        if lat is not None and lon is not None:
            return lat, lon
    return None, None


def find_sequences(
    sorted_entries: List[ImageEntry],
    n: int,
    max_gap_seconds: int,
) -> List[List[ImageEntry]]:
    """Find non-overlapping sequences of exact length `n` where consecutive images have gaps <= max_gap_seconds.

    Args:
        sorted_entries: image entries sorted by timestamp ascending.
        n: required sequence length.
        max_gap_seconds: maximum allowed gap between consecutive images.

    Returns:
        List of sequences (each sequence is a list of ImageEntry).

    """
    if n <= 0:
        return []

    res: List[List[ImageEntry]] = []
    m = len(sorted_entries)
    if m < n:
        return res

    current: List[ImageEntry] = []
    for entry in sorted_entries:
        if not current:
            current.append(entry)
            continue

        gap = (entry.ts - current[-1].ts).total_seconds()
        if gap < 0 or gap > max_gap_seconds:
            current = [entry]
            continue

        current.append(entry)
        if len(current) == n:
            res.append(current)
            current = []
    return res


def xyxy_to_yolo(x1: float, y1: float, x2: float, y2: float) -> Optional[Tuple[float, float, float, float]]:
    """Convert normalized xyxy box to YOLO normalized cx, cy, w, h."""
    if x2 <= x1 or y2 <= y1:
        return None
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    w = x2 - x1
    h = y2 - y1
    return cx, cy, w, h


def scan_folder_for_sequences(
    folder: Path,
    n: int,
    max_gap_seconds: int,
) -> List[List[ImageEntry]]:
    """Scan one folder and return sequences of images meeting the criteria."""
    entries: List[ImageEntry] = []
    for p in sorted(folder.glob("*.jpg")):
        ts = parse_timestamp_from_filename(p.name)
        if ts is None:
            continue
        entries.append(ImageEntry(p, ts))
    entries.sort(key=lambda e: e.ts)
    return find_sequences(entries, n=n, max_gap_seconds=max_gap_seconds)


def iter_leaf_folders(root: Path) -> Iterable[Path]:
    """Yield leaf folders under `root` that contain images.

    The scrapy pipeline organizes images under `images/<cam_id>/<azimuth>/`.
    This function yields each `<azimuth>` folder.
    """
    if not root.exists():
        return []
    # Expect two-level nesting: cam_id / azimuth / files
    for cam_dir in root.iterdir():
        if not cam_dir.is_dir():
            continue
        for az_dir in cam_dir.iterdir():
            if not az_dir.is_dir():
                continue
            yield az_dir


def run_inference_on_sequence(
    engine: Engine, sequence: List[ImageEntry], min_detections: int = 3
) -> tuple[bool, float, Dict[Path, List[Tuple[int, float, float, float, float]]]]:
    """Run pyroengine inference on a sequence of images.

    Args:
        engine: pyroengine Engine instance.
        sequence: list of ImageEntry objects in temporal order.
        min_detections: minimum number of images with fire detection required.

    Returns:
        Tuple of (has_detection, average_confidence, labels_by_path).

    """
    # Reset Engine state to avoid contamination between sequences
    # The engine maintains a temporal buffer that persists across predict() calls
    engine._states["-1"]["last_predictions"].clear()
    engine._states["-1"]["ongoing"] = False
    engine._states["-1"]["anchor_bbox"] = None

    raw_confidences = []  # Raw model confidences (last bbox confidence)
    labels_by_path: Dict[Path, List[Tuple[int, float, float, float, float]]] = {}
    detections_count = 0

    for entry in sequence:
        try:
            img = Image.open(entry.path).convert("RGB")
            # Use model directly to get raw predictions without temporal aggregation
            _, bbox_mask_dict, _ = engine.occlusion_masks["-1"]
            preds = engine.model(img, bbox_mask_dict)  # Returns np.array with shape (N, 5): [x1, y1, x2, y2, conf]

            # Get maximum confidence from all detected boxes
            max_conf = float(preds[:, 4].max()) if preds.size > 0 else 0.0
            raw_confidences.append(max_conf)

            labels: List[Tuple[int, float, float, float, float]] = []
            for x1, y1, x2, y2, _ in preds:
                yolo_box = xyxy_to_yolo(float(x1), float(y1), float(x2), float(y2))
                if yolo_box is None:
                    continue
                cx, cy, w, h = yolo_box
                labels.append((0, cx, cy, w, h))
            labels_by_path[entry.path] = labels

            if max_conf > engine.conf_thresh:  # Count images with fire detected (conf > 0.15)
                detections_count += 1

            logging.info(
                f"    Image {entry.path.name}: max_conf={max_conf:.4f} (detected: {max_conf > engine.conf_thresh})"
            )
        except Exception as e:
            print(f"  Error processing {entry.path.name}: {e}")
            continue

    avg_conf = sum(raw_confidences) / len(raw_confidences) if raw_confidences else 0.0
    has_fire = detections_count >= min_detections

    logging.info(f"  Detections: {detections_count}/{len(sequence)} images with fire (threshold: {min_detections})")
    logging.info(f"  Average confidence: {avg_conf:.4f}")

    return has_fire, avg_conf, labels_by_path
