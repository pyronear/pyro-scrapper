"""Pipeline orchestration for wildfire detection and annotation API submission.

This is the main orchestration script that coordinates:
1. Temporal image sequence detection (via inference.py)
2. Pyroengine fire detection inference (via inference.py)
3. Annotation API submission (via send_annotation_api.py)

This script serves as the bridge between the scrapy image collection pipeline
and the pyro-annotator API, and is called by continuous_workflow.py.

Filename convention expected from the pipeline:
    <cam_id>_<YYYYMMDD>_<HHMMSS>_<microseconds>_<lat>_<lon>_<cam_name>.jpg

Example:
    CAM123_20250212_153000_123456_43.6047_1.4442_Ben_Bolte_2.jpg

Usage (from repo root or the alertwest_scraping folder):
    python alertwest_scraping/orchestration_inference_send_annotation_api.py --n 6 --max-gap 60
Make sure max-gap is set according to the frequency time of scraping
(e.g., not less than 60 seconds if images are scraped every minute)
to find valid sequences.

"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure repo root is on sys.path when running as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pyroengine.core import Engine

from alertwest_scraping.send_annotation_api import (
    ANNOTATION_ALERT_API_ID,
    find_folder_cam_id_and_name,
    generate_alert_api_id,
    import_sequence_via_annotation_api,
    parse_azimuth,
)
from alertwest_scraping.config import (INTERVAL, MIN_DETECTIONS, CONF_THRESH) 
from alertwest_scraping.inference import (
    find_folder_lat_lon,
    iter_leaf_folders,
    run_inference_on_sequence,
    scan_folder_for_sequences,
)

def images_root_from_this_file() -> Path:
    """Return the root images directory produced by scrapy.

    Assumes this file lives in `pyro-scrapper/alertwest_scraping/` and images are
    in `pyro-scrapper/alertwest_scraping/images/`.
    """
    here = Path(__file__).parent
    return here / "images"


def run_inference_pipeline(
    images_dir: Path,
    n_consecutive: int = 6,
    max_gap_seconds: int = INTERVAL * 1.5,
    min_detections: int = 6 / 2,  # Minimum images with fire detection (default: half of sequence)
    logger: Optional[logging.Logger] = None,
) -> int:
    """Run the complete inference pipeline on collected images.

    This is the main orchestration entry point. It:
    1. Scans images for temporal sequences (via inference.py)
    2. Runs fire detection on each sequence (via inference.py)
    3. Submits positive detections to the API (via send_annotation_api.py)

    Args:
        images_dir: Root images directory path.
        n_consecutive: Required number of consecutive images in a sequence.
        max_gap_seconds: Maximum allowed gap between consecutive images in seconds.
        min_detections: Minimum number of images with fire detection (conf > 0.15) to trigger alert.
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
        engine = Engine(conf_thresh=CONF_THRESH)  # Fixed: conf_thresh not conf_tresh
        log.info(f"✅ Engine loaded with confidence threshold: {CONF_THRESH}")
        log.info(f"✅ Sequence detection requires {min_detections}/{n_consecutive} images with fire")
    except Exception as e:
        log.error(f"❌ Error loading pyroengine: {e}")
        raise

    total_folders = 0
    total_sequences = 0
    total_detections = 0

    log.info(f"📸 Processing images from: {images_dir}")
    log.info("💾 Local copies disabled: sending detections directly to API")
    log.info(f"🔍 Looking for sequences of {n_consecutive} images with max gap of {max_gap_seconds}s")

    for folder in iter_leaf_folders(images_dir):
        total_folders += 1
        seqs = scan_folder_for_sequences(
            folder,
            n=n_consecutive,
            max_gap_seconds=max_gap_seconds,
        )
        if not seqs:
            continue

        total_sequences += len(seqs)
        cam_id, cam_name = find_folder_cam_id_and_name(folder)
        azimuth = folder.name

        lat, lon = find_folder_lat_lon(folder)
        missing_lat_lon = lat is None or lon is None
        if missing_lat_lon:
            log.warning(
                "Missing lat/lon for camera %s (azimuth %s): skipping API import for this folder",
                cam_id,
                azimuth,
            )
        # log.info(f"📁 [{total_folders}] Camera {cam_id} (azimuth {azimuth}) - Found {len(seqs)} sequence(s)")

        # Process each sequence with pyroengine
        for idx, seq in enumerate(seqs, 1):
            first_ts = seq[0].ts.strftime("%Y%m%d_%H%M%S")
            last_ts = seq[-1].ts.strftime("%Y%m%d_%H%M%S")
            log.info(
                f"  Sequence #{idx}: {first_ts} -> {last_ts} ({len(seq)} images)",
            )

            has_detection, avg_conf, labels_by_path = run_inference_on_sequence(
                engine,
                seq,
                min_detections,
            )
            # log.info("    Average confidence: %.4f", avg_conf)

            if has_detection:
                # log.info(" 🔥 DETECTION!")
                
                alert_api_id = ANNOTATION_ALERT_API_ID
                if alert_api_id is None:
                    alert_api_id = generate_alert_api_id(cam_id, azimuth, seq[0].ts)

                import_sequence_via_annotation_api(
                    seq,
                    cam_id,
                    cam_name,
                    parse_azimuth(azimuth),
                    lat,
                    lon,
                    alert_api_id,
                    labels_by_path,
                    log,
                )
            else:
                log.info(" (no detection)")

    log.info(f"\n{'=' * 70}")
    log.info("📊 Inference Summary:")
    log.info(f"   Scanned folders: {total_folders}")
    log.info(f"   Valid sequences found: {total_sequences}")
    log.info(f"   Folders with fire detections: {total_detections}")
    log.info(f"{'=' * 70}")

    return total_detections


def main(
    images_dir: Optional[str],
    n: int,
    max_gap_seconds: int,
    min_detections: int,
    ) -> int:
    """Process image sequences and run detection.

    Args:
        images_dir: Root images directory path.
        n: Required number of consecutive images.
        max_gap_seconds: Maximum allowed gap between consecutive images.
        min_detections: Minimum number of images with fire detection.

    Returns:
        Exit code (0 for success, 1 for error).

    """
    root = Path(images_dir) if images_dir else images_root_from_this_file()

    try:
        run_inference_pipeline(
            images_dir=root,
            n_consecutive=n,
            max_gap_seconds=max_gap_seconds,
            min_detections=min_detections,
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
        "--min-detections",
        type=int,
        default=MIN_DETECTIONS,  # Half of 6 images by default
        help="Minimum number of images with fire detection (conf > 0.15) to trigger alert",
    )
    args = parser.parse_args()

    raise SystemExit(main(args.images_dir, args.n, args.max_gap, args.min_detections))
