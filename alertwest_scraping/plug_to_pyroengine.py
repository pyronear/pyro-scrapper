"""Utilities to bridge pyro-scrapper images with pyroengine.

This script scans the `images/` folder produced by the scrapy pipeline,
groups images by their containing folder (typically `cam_id/azimuth/`),
extracts timestamps from filenames, and finds sequences of N images where
each consecutive pair is separated by at most `max_gap_seconds`.

Filename convention expected from the pipeline:
    <cam_id>_<YYYYMMDD>_<HHMMSS>_<microseconds>.jpg

Example:
    CAM1_20250101_120000_123456.jpg

Usage (from repo root or the alertwest_scraping folder):
    python alertwest_scraping/plug_to_pyroengine.py --n 6 --max-gap 60
Make sure max-gap is set according to the frequency time of scraping 
(e.g., not less than 60 seconds if images are scraped every minute) 
to find valid sequences.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
from alertwest_scraping.config import INTERVAL

from PIL import Image
from pyroengine.core import Engine

TIMESTAMP_FMT = "%Y%m%d_%H%M%S_%f"


@dataclass
class ImageEntry:
    """Container for image path and timestamp."""

    path: Path
    ts: datetime


def images_root_from_this_file() -> Path:
    """Return the root images directory produced by scrapy.

    Assumes this file lives in `pyro-scrapper/alertwest_scraping/` and images are
    in `pyro-scrapper/alertwest_scraping/images/`.
    """
    here = Path(__file__).parent
    return here / "images"


def parse_timestamp_from_filename(name: str) -> Optional[datetime]:
    """Extract timestamp from filename based on pipeline pattern.

    Expected pattern: CAMID_YYYYMMDD_HHMMSS_MICRO.jpg
    Returns None if it doesn't match or parses.
    """
    base = os.path.basename(name)
    # split on first underscore (cam_id), then expect ts components
    try:
        cam_id, rest = base.split("_", 1)
        # rest should be like YYYYMMDD_HHMMSS_MICRO.jpg
        stem, ext = os.path.splitext(rest)
        parts = stem.split("_")
        if len(parts) != 3:
            return None
        ts_str = "_".join(parts)
        return datetime.strptime(ts_str, TIMESTAMP_FMT)
    except Exception:
        return None


def find_sequences(sorted_entries: List[ImageEntry], n: int, max_gap_seconds: int) -> List[List[ImageEntry]]:
    """Find sequences of length `n` where every consecutive gap ≤ `max_gap_seconds`.

    Args:
        sorted_entries: image entries sorted by timestamp ascending.
        n: required sequence length.
        max_gap_seconds: maximum allowed gap between consecutive images.

    Returns:
        List of sequences (each sequence is a list of ImageEntry).

    """
    if n <= 1:
        return [[e] for e in sorted_entries]

    res: List[List[ImageEntry]] = []
    m = len(sorted_entries)
    if m < n:
        return res

    # Sliding window check of consecutive gaps
    for i in range(0, m - n + 1):
        window = sorted_entries[i : i + n]
        ok = True
        for a, b in zip(window, window[1:]):
            gap = (b.ts - a.ts).total_seconds()
            if gap < 0 or gap > max_gap_seconds:
                ok = False
                break
        if ok:
            res.append(window)
    return res


def scan_folder_for_sequences(folder: Path, n: int, max_gap_seconds: int) -> List[List[ImageEntry]]:
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
    engine: Engine, sequence: List[ImageEntry], conf_thresh: float = 0.15
) -> tuple[bool, float]:
    """Run pyroengine inference on a sequence of images.

    Args:
        engine: pyroengine Engine instance.
        sequence: list of ImageEntry objects in temporal order.
        conf_thresh: confidence threshold to consider a detection positive.

    Returns:
        Tuple of (has_detection, max_confidence).

    """
    max_conf = 0.0
    for entry in sequence:
        try:
            img = Image.open(entry.path).convert("RGB")
            conf = engine.predict(img)
            if conf > max_conf:
                max_conf = conf
        except Exception as e:
            print(f"  Error processing {entry.path.name}: {e}")
            continue

    return max_conf >= conf_thresh, max_conf


def handle_detection(folder: Path, sequence: List[ImageEntry], output_dir: Path) -> None:
    """Copy or move the folder containing detected sequence to output directory.

    Args:
        folder: the folder containing the sequence images.
        sequence: the sequence that triggered detection.
        output_dir: destination directory for annotations.

    """
    output_dir.mkdir(parents=True, exist_ok=True)
    # Copy entire folder structure: cam_id/azimuth/
    cam_id = folder.parent.name
    azimuth = folder.name
    dest_folder = output_dir / cam_id / azimuth

    if dest_folder.exists():
        print(f"  Destination already exists: {dest_folder}")
        return

    try:
        shutil.copytree(folder, dest_folder)
        print(f"  ✓ Copied {folder} -> {dest_folder}")
    except Exception as e:
        print(f"  Error copying {folder}: {e}")


def run_inference_pipeline(
    images_dir: Path,
    output_dir: Path,
    n_consecutive: int = 6,
    max_gap_seconds: int = 120,
    conf_thresh: float = 0.15,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Run the complete inference pipeline on collected images.

    This is the main entry point for the inference workflow. It processes all
    images in the images directory, detects fire sequences, and saves results
    to the annotations directory.

    Args:
        images_dir: Root images directory path.
        output_dir: Output directory for detected sequences.
        n_consecutive: Required number of consecutive images in a sequence.
        max_gap_seconds: Maximum allowed gap between consecutive images in seconds.
        conf_thresh: Confidence threshold for fire detection.
        logger: Optional logger instance (defaults to print statements).

    Returns:
        Number of folders with detections.

    Raises:
        Exception: If pyroengine fails to initialize.

    """
    log = logger or logging.getLogger(__name__)

    if not images_dir.exists():
        log.warning(f"Images directory not found: {images_dir}")
        return 0

    log.info("🔥 Initializing pyroengine for inference...")
    try:
        engine = Engine()
        log.info(f"✅ Engine loaded with confidence threshold: {conf_thresh}")
    except Exception as e:
        log.error(f"❌ Error loading pyroengine: {e}")
        raise

    total_folders = 0
    total_sequences = 0
    total_detections = 0
    processed_folders = set()

    log.info(f"📸 Processing images from: {images_dir}")
    log.info(f"💾 Detection output directory: {output_dir}")
    log.info(f"🔍 Looking for sequences of {n_consecutive} images with max gap of {max_gap_seconds}s")

    for folder in iter_leaf_folders(images_dir):
        total_folders += 1
        seqs = scan_folder_for_sequences(folder, n=n_consecutive, max_gap_seconds=max_gap_seconds)
        if not seqs:
            continue

        total_sequences += len(seqs)
        cam_id = folder.parent.name
        azimuth = folder.name
        log.info(f"📁 [{total_folders}] Camera {cam_id} (azimuth {azimuth}) - Found {len(seqs)} sequence(s)")

        # Process each sequence with pyroengine
        for idx, seq in enumerate(seqs, 1):
            first_ts = seq[0].ts.strftime("%Y%m%d_%H%M%S")
            last_ts = seq[-1].ts.strftime("%Y%m%d_%H%M%S")
            log.info(
                f"  Sequence #{idx}: {first_ts} -> {last_ts} ({len(seq)} images)",
            )

            has_detection, max_conf = run_inference_on_sequence(engine, seq, conf_thresh)
            log.info(f"    Max confidence: {max_conf:.4f}", end="")

            if has_detection:
                log.info(" 🔥 DETECTION!")
                # Only copy folder once even if multiple sequences detected
                if folder not in processed_folders:
                    handle_detection(folder, seq, output_dir)
                    processed_folders.add(folder)
                    total_detections += 1
            else:
                log.info(" (no detection)")

    log.info(f"\n{'=' * 70}")
    log.info("📊 Inference Summary:")
    log.info(f"   Scanned folders: {total_folders}")
    log.info(f"   Valid sequences found: {total_sequences}")
    log.info(f"   Folders with fire detections: {total_detections}")
    log.info(f"   Results saved to: {output_dir}")
    log.info(f"{'=' * 70}")

    return total_detections


def main(
    images_dir: Optional[str],
    n: int,
    max_gap_seconds: int,
    conf_thresh: float,
    output_dir: Optional[str],
) -> int:
    """Process image sequences and run detection.

    Args:
        images_dir: Root images directory path.
        n: Required number of consecutive images.
        max_gap_seconds: Maximum allowed gap between consecutive images.
        conf_thresh: Confidence threshold for detection.
        output_dir: Output directory for detected sequences.

    Returns:
        Exit code (0 for success, 1 for error).

    """
    root = Path(images_dir) if images_dir else images_root_from_this_file()
    output_path = Path(output_dir) if output_dir else root.parent / "annotations"

    try:
        run_inference_pipeline(
            images_dir=root,
            output_dir=output_path,
            n_consecutive=n,
            max_gap_seconds=max_gap_seconds,
            conf_thresh=conf_thresh,
        )
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find consecutive image sequences and run pyroengine detection.")
    parser.add_argument(
        "--images-dir",
        type=str,
        default=None,
        help="Root images directory (defaults to images/ next to this file)",
    )
    parser.add_argument("--n", type=int, default=6, help="Required number of consecutive images")
    parser.add_argument(
        "--max-gap",
        type=int,
        default=INTERVAL * 1.5,
        help="Maximum allowed gap in seconds between consecutive images",
    )
    parser.add_argument(
        "--conf-thresh",
        type=float,
        default=0.15,
        help="Confidence threshold for detection",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for detected sequences (defaults to annotations/ next to images)",
    )
    args = parser.parse_args()

    raise SystemExit(main(args.images_dir, args.n, args.max_gap, args.conf_thresh, args.output_dir))
