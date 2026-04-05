"""Pipeline orchestration for wildfire detection and annotation API submission.

This is the main orchestration script that coordinates:
1. Temporal image sequence detection directly with Predictor
2. Predictor fire detection inference with sliding-window state
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
import zlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

PREDICTOR_ROOT = Path(__file__).resolve().parents[2] / "pyro-engine" / "pyro-predictor"
if PREDICTOR_ROOT.exists() and str(PREDICTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(PREDICTOR_ROOT))

if __package__ in (None, ""):
    # Ensure repo root is on sys.path when running as a script.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    from alertwest_scraping.config import CONF_THRESH, FRAME_SIZE, MAX_GAP_SECONDS, MODEL_CONF_THRESH, N_CONSECUTIVE
    from alertwest_scraping.send_annotation_api import import_sequence_via_annotation_api
    from alertwest_scraping.utils_inference_annotation import (
        ImageEntry,
        find_folder_metadata,
        iter_leaf_folders,
        scan_folder_images,
        xyxy_to_yolo,
    )
    from pyro_predictor import Predictor
else:
    from .config import CONF_THRESH, FRAME_SIZE, MAX_GAP_SECONDS, MODEL_CONF_THRESH, N_CONSECUTIVE
    from .send_annotation_api import import_sequence_via_annotation_api
    from .utils_inference_annotation import (
        ImageEntry,
        find_folder_metadata,
        iter_leaf_folders,
        scan_folder_images,
        xyxy_to_yolo,
    )
    from pyro_predictor import Predictor

TIMESTAMP_FMT = "%Y%m%d_%H%M%S"


def build_labels_by_path(
    predictor: Predictor,
    sequence: List[ImageEntry],
    cam_key: str,
) -> Dict[Path, List[Tuple[int, float, float, float, float, float]]]:
    """Extract YOLO labels from the Predictor's internal buffer (no re-inference).

    The Predictor already maintains a buffer of raw model predictions per frame.
    This function reuses those cached predictions instead of re-running the model,
    ensuring that the boxes sent to the API match exactly what triggered the alert.

    Args:
        predictor: Predictor instance with internal state
        sequence: List of ImageEntry to extract labels for
        cam_key: Camera key for state lookup (e.g., "cam_id_azimuth")

    Returns:
        Dict mapping image paths to list of (class_id, cx, cy, w, h, confidence) tuples

    """
    labels_by_path: Dict[Path, List[Tuple[int, float, float, float, float, float]]] = {}

    # Access the Predictor's internal buffer for this camera
    if cam_key not in predictor._states:
        return labels_by_path

    state = predictor._states[cam_key]
    buffer_predictions = state["last_predictions"]

    # Extract predictions for the sequence
    # Note: buffer_predictions is a deque(maxlen=8), so older entries may have been discarded
    for entry, (frame, preds, _, _, _) in zip(sequence, list(buffer_predictions)):
        labels: List[Tuple[int, float, float, float, float, float]] = []

        for pred in preds:
            x1, y1, x2, y2, score = pred[:5]
            yolo_box = xyxy_to_yolo(float(x1), float(y1), float(x2), float(y2))
            if yolo_box is None:
                continue
            cx, cy, w, h = yolo_box
            confidence = max(0.0, min(1.0, float(score)))
            labels.append((0, cx, cy, w, h, confidence))

        labels_by_path[entry.path] = labels

    return labels_by_path


def generate_alert_api_id(cam_id: str, azimuth: str, recorded_at: datetime) -> int:
    """Generate a deterministic, collision-free CRC32 sequence identifier.

    Args:
        cam_id: camera identifier.
        azimuth: camera azimuth.
        recorded_at: first image timestamp in sequence.

    Returns:
        32-bit CRC32 hash as unsigned integer.

    """
    seed = f"{cam_id}:{azimuth}:{recorded_at.isoformat()}"
    return zlib.crc32(seed.encode("utf-8")) & 0x7FFFFFFF


def run_inference_pipeline(
    images_dir: Path,
    conf_thresh: float = CONF_THRESH,
    model_conf_thresh: float = MODEL_CONF_THRESH,
    n_consecutive: int = N_CONSECUTIVE,
    max_gap_seconds: float = MAX_GAP_SECONDS,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Run the complete inference pipeline on collected images.

    This is the main orchestration entry point. It:
    1. Scans images for temporal sequences directly in this module
    2. Runs fire detection on each frame with Predictor
    3. Submits positive detections to the API (via send_annotation_api.py)

    The `alert_active` flag prevents duplicate API submissions for the same
    continuous fire event. Once a sequence has been sent, the pipeline waits
    for the confidence to drop below the threshold before allowing another
    alert to be emitted.

    Args:
        images_dir: Root images directory path.
        conf_thresh: Confidence threshold for considering a detection as an alert.
        model_conf_thresh: Confidence threshold passed to the Predictor's model.
        n_consecutive: Number of consecutive frames required to trigger an alert.
        max_gap_seconds: Maximum allowed time gap between frames in a sequence.
        logger: Optional logger instance (defaults to print statements).

    Returns:
        Number of folders with detections.

    """
    log = logger or logging.getLogger(__name__)

    # Loading predictor
    log.info("🔥 Initializing predictor for inference...")
    try:
        predictor = Predictor(
            conf_thresh=conf_thresh,
            model_conf_thresh=model_conf_thresh,
            nb_consecutive_frames=n_consecutive,
            frame_size=FRAME_SIZE,
            verbose=False,
        )
        log.info(f"✅ Predictor loaded with model confidence threshold: {model_conf_thresh}")
        log.info(f"✅ Alert threshold set to predictor confidence > {conf_thresh}")
    except Exception as e:
        log.error(f"❌ Error loading predictor: {e}")
        raise

    total_folders = 0
    total_sequences = 0
    total_detections = 0

    # Step 1 :
    log.info(f"🔍 Looking for sequences of {n_consecutive} images with max gap of {max_gap_seconds}s")
    for folder in iter_leaf_folders(images_dir):
        total_folders += 1
        cam_id, cam_name, lat, lon = find_folder_metadata(folder)
        azimuth = folder.name
        if azimuth == "unknown":
            int_azimuth = -666
        else :
            int_azimuth =int(round(float(azimuth)))
            
        # At least N_CONSECUTIVE images are required to find a valid sequence
        entries = scan_folder_images(folder)
        if len(entries) < n_consecutive:
            continue

        log.info(f"📸 Processing images from camera {cam_id} (azimuth {azimuth})")
        cam_key = f"{cam_id}_{azimuth}"
        current_window: List[ImageEntry] = []
        previous_entry: Optional[ImageEntry] = None
        # Prevent duplicate API submissions for the same continuous fire event.
        # Once an alert has been sent, this flag blocks further sends until the
        # model confidence drops below the threshold again.
        alert_active = False

        for entry in entries:
            if previous_entry is not None:
                gap_seconds = (entry.ts - previous_entry.ts).total_seconds()
                if gap_seconds < 0 or gap_seconds > MAX_GAP_SECONDS:
                    predictor = Predictor(
                        conf_thresh=conf_thresh,
                        model_conf_thresh=model_conf_thresh,
                        nb_consecutive_frames=n_consecutive,
                        frame_size=FRAME_SIZE,
                        verbose=False,
                    )
                    current_window = []
                    alert_active = False
                    log.info(
                        "🔁 Resetting predictor for camera %s after gap of %.1fs",
                        cam_key,
                        gap_seconds,
                    )

            previous_entry = entry
            current_window.append(entry)
            # Actualize the sequence of n_consecutive frames
            if len(current_window) > n_consecutive:
                current_window.pop(0)

            with Image.open(entry.path) as image:
                confidence = predictor.predict(image.convert("RGB"), cam_id=cam_key)

            if confidence > conf_thresh:
                if len(current_window) == n_consecutive and not alert_active:
                    # Build one payload per frame in the window and submit it
                    # only once for the current alert event.
                    # Each box keeps the confidence returned by the raw model.
                    labels_by_path = build_labels_by_path(predictor, current_window, cam_key)
                    alert_api_id = generate_alert_api_id(cam_id, azimuth, current_window[0].ts)

                    # Print les valeurs de confidence pour chaque détection dans la séquence
                    for path, labels in labels_by_path.items():
                        for label in labels:
                            _, _, _, _, _, conf = label
                            log.info(f"   Detected confidence {conf:.4f} for image {path.name}")

                    import_sequence_via_annotation_api(
                        current_window,
                        cam_id,
                        cam_name,
                        int_azimuth,
                        lat,
                        lon,
                        alert_api_id,
                        labels_by_path,
                        log,
                    )
                    total_sequences += 1
                    total_detections += 1
                    alert_active = True
                    log.info(
                        "🔥 Sent %s frame window for camera %s at confidence %.4f",
                        N_CONSECUTIVE,
                        cam_key,
                        confidence,
                    )
            else:
                alert_active = False

    log.info(f"\n{'=' * 70}")
    log.info("📊 Inference Summary:")
    log.info(f"   Scanned folders: {total_folders}")
    log.info(f"   Alert sequences sent: {total_sequences}")
    log.info(f"   Folders with fire detections: {total_detections}")
    log.info(f"{'=' * 70}")

    return total_detections


def main(
    images_dir: Optional[str],
    logger: Optional[logging.Logger] = None,
) -> int:
    """Process image sequences and run detection.

    Args:
        images_dir: Root images directory path.
        logger: Optional logger instance (defaults to print statements).

    Returns:
        Exit code (0 for success, 1 for error).

    """
    here = Path(__file__).parent
    root = Path(images_dir) if images_dir else here / "images"
    log = logger or logging.getLogger(__name__)

    # Test if images directory is not none type or does exist
    if not root.exists() or not root.is_dir():
        log.warning(f"Images directory not found: {images_dir}")
        return 0

    try:
        run_inference_pipeline(
            images_dir=root,
        )
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find consecutive image sequences and run predictor detection.")
    parser.add_argument(
        "--images-dir",
        type=str,
        default=None,
        help="Root images directory (defaults to images/ next to this file)",
    )
    parser.add_argument(
        "--logger",
        type=str,
        default=None,
        help="Logger name (defaults to __name__)",
    )
    args = parser.parse_args()

    raise SystemExit(main(args.images_dir, logger=logging.getLogger(args.logger)))
