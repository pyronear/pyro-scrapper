"""Annotation API integration for sequence ingestion.

This module handles submission of detected fire sequences to the pyro-annotator
API. It manages credential loading, YOLO format directory creation, and subprocess
invocation of the annotation import script.

"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ANNOTATION_API_BASE = "https://annotationapi.pyronear.org/"
ANNOTATION_ALERT_API_ID = None  # None enables per-sequence generation
ANNOTATION_ORG_ID = 1
ANNOTATION_ORG_NAME = "alert_west"
ANNOTATION_SOURCE_API = "alert_wildfire"
ANNOTATION_SEQUENCE_STAGE = "ready_to_annotate"


def parse_cam_id_and_name_from_filename(name: str) -> Optional[str]:
    """Extract camera name from filename suffix if present."""
    base = os.path.basename(name)
    try:
        _, rest = base.split("_", 1)
        stem, _ = os.path.splitext(rest)
        parts = stem.split("_")
        if len(parts) < 6:
            return None
        cam_id = parts[0]
        cam_name = "_".join(parts[5:]).strip() 
        return cam_id, cam_name or None
    except (ValueError, TypeError):
        return None


def find_folder_cam_id_and_name(folder: Path) -> Optional[str]:
    """Return the first camera name found in the folder's filenames."""
    for image_path in folder.glob("*.jpg"):
        cam_id, cam_name = parse_cam_id_and_name_from_filename(image_path.name)
        return cam_id, cam_name
    


def parse_azimuth(value: str) -> Optional[int]:
    """Parse azimuth string to int when possible."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def create_yolo_sequence_dir(
    sequence,
    output_dir: Path,
    cam_id: str,
    azimuth: str,
    labels_by_path: Optional[dict[Path, list[tuple[int, float, float, float, float]]]] = None,
) -> Path:
    """Create a YOLO-compatible sequence folder with images and labels.

    Args:
        sequence: list of ImageEntry objects with path and ts attributes.
        output_dir: root output directory for sequences.
        cam_id: camera identifier string.
        azimuth: camera azimuth string.

    Returns:
        Path to the created sequence directory.

    """
    seq_start = sequence[0].ts.strftime("%Y%m%d_%H%M%S_%f")
    seq_root = output_dir / "api_sequences" / f"{cam_id}_{azimuth}_{seq_start}"
    images_dir = seq_root / "images"
    labels_dir = seq_root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    for entry in sequence:
        recorded_at = entry.ts.strftime("%Y-%m-%dT%H-%M-%S")
        image_name = (
            f"pyronear-{ANNOTATION_ORG_NAME}-{cam_id}-{azimuth}-{recorded_at}.jpg"
        )
        dest_image = images_dir / image_name
        shutil.copy2(entry.path, dest_image)
        label_path = labels_dir / f"{dest_image.stem}.txt"
        labels = [] if labels_by_path is None else labels_by_path.get(entry.path, [])
        if labels:
            lines = [f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cls_id, cx, cy, w, h in labels]
            label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            label_path.write_text("", encoding="utf-8")

    return seq_root


def generate_alert_api_id(cam_id: str, azimuth: str, recorded_at: datetime) -> int:
    """Generate a stable alert_api_id per sequence to avoid collisions.

    Uses CRC32 hash of the sequence identifier to create a deterministic,
    collision-free unique ID.

    Args:
        cam_id: camera identifier.
        azimuth: camera azimuth.
        recorded_at: first image timestamp in sequence.

    Returns:
        32-bit CRC32 hash as unsigned integer.

    """
    seed = f"{cam_id}:{azimuth}:{recorded_at.isoformat()}"
    return zlib.crc32(seed.encode("utf-8")) & 0x7FFFFFFF


def normalize_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/api/v1"):
        return trimmed[: -len("/api/v1")]
    return trimmed


def ensure_annotation_api_importable() -> Optional[Path]:
    """Ensure pyro-annotator annotation_api is importable from this repo."""
    repo_root = Path(__file__).resolve().parents[2]
    annotation_root = repo_root / "pyro-annotator" / "annotation_api"
    if not annotation_root.exists():
        return None
    sys.path.insert(0, str(annotation_root))
    sys.path.insert(0, str(annotation_root / "src"))
    return annotation_root


def load_annotation_env(annotation_root: Path, logger: logging.Logger) -> None:
    """Load credentials from pyro-annotator .env when available."""
    env_path = annotation_root / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except Exception as exc:
        logger.warning("Unable to import python-dotenv: %s", exc)
        return
    load_dotenv(dotenv_path=env_path, override=False)


def import_sequence_via_annotation_api(
    sequence,
    cam_id: str,
    cam_name: str,
    azimuth: Optional[int],
    lat: float,
    lon: float,
    alert_api_id: int,
    labels_by_path: Dict[Path, List[Tuple[int, float, float, float, float]]],
    logger: logging.Logger,
) -> None:
    """Send a sequence directly to the annotation API without local copies."""
    annotation_root = ensure_annotation_api_importable()
    if not annotation_root:
        logger.warning("Missing pyro-annotator repo. Skipping API import.")
        return

    load_annotation_env(annotation_root, logger)

    try:
        from app.clients import annotation_api
        from scripts.data_transfer.ingestion.platform.shared import (
            get_annotation_credentials,
        )
    except Exception as exc:
        logger.warning("Unable to import annotation_api client: %s", exc)
        return

    base_url = normalize_base_url(ANNOTATION_API_BASE)
    username, password = get_annotation_credentials(base_url)

    try:
        token = annotation_api.get_auth_token(base_url, username, password)
    except Exception as exc:
        logger.warning("API auth failed: %s", exc)
        return

    image_infos: List[Tuple[Path, datetime]] = [(entry.path, entry.ts) for entry in sequence]
    image_infos.sort(key=lambda item: item[1])
    if not image_infos:
        logger.warning("Empty sequence for cam %s", cam_id)
        return

    seq_recorded_at = image_infos[0][1]
    seq_last_seen_at = image_infos[-1][1]
    sequence_payload = {
        "source_api": ANNOTATION_SOURCE_API,
        "alert_api_id": alert_api_id,
        "camera_name": cam_name,
        "camera_id": int(cam_id),
        "organisation_name": ANNOTATION_ORG_NAME,
        "organisation_id": ANNOTATION_ORG_ID,
        "is_wildfire_alertapi": "wildfire_smoke",
        "lat": lat,
        "lon": lon,
        "azimuth": azimuth,
        "recorded_at": seq_recorded_at.isoformat(),
        "last_seen_at": seq_last_seen_at.isoformat(),
    }

    try:
        sequence_resp = annotation_api.create_sequence(base_url, token, sequence_payload)
    except Exception as exc:
        logger.warning("API create sequence failed: %s", exc)
        return

    seq_id = sequence_resp["id"]
    bboxes_by_class: Dict[int, List[Dict]] = {}
    detection_alert_id = 1

    for image_path, recorded_at in image_infos:
        labels = labels_by_path.get(image_path, [])
        predictions = []
        for class_id, cx, cy, w, h in labels:
            class_name = "wildfire"
            xyxyn = [
                max(0.0, min(1.0, cx - w / 2.0)),
                max(0.0, min(1.0, cy - h / 2.0)),
                max(0.0, min(1.0, cx + w / 2.0)),
                max(0.0, min(1.0, cy + h / 2.0)),
            ]
            predictions.append(
                {
                    "xyxyn": xyxyn,
                    "confidence": 1.0,
                    "class_name": class_name,
                }
            )

        detection_payload = {
            "algo_predictions": {"predictions": predictions},
            "alert_api_id": detection_alert_id,
            "sequence_id": seq_id,
            "recorded_at": recorded_at.isoformat(),
        }
        detection_alert_id += 1

        try:
            detection = annotation_api.create_detection(
                base_url,
                token,
                detection_payload,
                image_path.read_bytes(),
                image_path.name,
            )
        except Exception as exc:
            logger.warning("API create detection failed for %s: %s", image_path.name, exc)
            continue

        det_id = detection["id"]
        for class_id, cx, cy, w, h in labels:
            xyxyn = [
                max(0.0, min(1.0, cx - w / 2.0)),
                max(0.0, min(1.0, cy - h / 2.0)),
                max(0.0, min(1.0, cx + w / 2.0)),
                max(0.0, min(1.0, cy + h / 2.0)),
            ]
            bboxes_by_class.setdefault(class_id, []).append(
                {"detection_id": det_id, "xyxyn": xyxyn}
            )

    sequences_bbox: List[Dict] = []
    for class_id, bboxes in bboxes_by_class.items():
        if not bboxes:
            continue
        sequences_bbox.append(
                {
                    "is_smoke": False,
                    "bboxes": bboxes,
                }
)

    annotation_payload = {
        "sequence_id": seq_id,
        "has_missed_smoke": False,
        "is_unsure": False,
        "annotation": {"sequences_bbox": sequences_bbox},
        "processing_stage": ANNOTATION_SEQUENCE_STAGE,
    }

    try:
        annotation_api.create_sequence_annotation(base_url, token, annotation_payload)
    except Exception as exc:
        logger.warning("API create sequence annotation failed: %s", exc)
