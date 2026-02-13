"""Annotation API integration for sequence ingestion.

This module handles submission of detected fire sequences to the pyro-annotator
API. It manages credential loading, YOLO format directory creation, and subprocess
invocation of the annotation import script.

"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import zlib
from datetime import datetime
from pathlib import Path
from typing import Optional


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
    sequence, output_dir: Path, cam_id: str, azimuth: str
) -> Path:
    """Create a YOLO-compatible sequence folder with images and empty labels.

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


def resolve_annotation_script_path() -> Optional[Path]:
    """Locate the import_yolo_sequence script from the pyro-annotator repo.

    Expects pyro-annotator to be in the same parent directory as pyro-scrapper.

    Returns:
        Path to import_yolo_sequence.py if found, None otherwise.

    """
    repo_root = Path(__file__).resolve().parents[2]
    script_path = (
        repo_root
        / "pyro-annotator"
        / "annotation_api"
        / "scripts"
        / "data_transfer"
        / "ingestion"
        / "platform"
        / "import_yolo_sequence.py"
    )
    return script_path if script_path.exists() else None


def build_annotation_env(annotation_root: Path) -> dict:
    """Ensure annotation_api src and scripts are on PYTHONPATH.

    Args:
        annotation_root: root directory of pyro-annotator/annotation_api.

    Returns:
        Environment dict with modified PYTHONPATH.

    """
    env = os.environ.copy()
    extra_paths = [str(annotation_root), str(annotation_root / "src")]
    existing = env.get("PYTHONPATH", "")
    if existing:
        extra_paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(extra_paths)
    return env


def import_sequence_via_annotation_api(
    sequence_dir: Path,
    cam_id: str,
    cam_name: str,
    azimuth: Optional[int],
    lat: float,
    lon: float,
    alert_api_id: int,
    logger: logging.Logger,
) -> None:
    """Invoke the annotation API import script for a sequence.

    Calls import_yolo_sequence.py via subprocess with all required parameters
    for API ingestion.

    Args:
        sequence_dir: path to the YOLO sequence directory.
        cam_id: camera identifier.
        cam_name: user-friendly camera name.
        azimuth: camera azimuth (or None).
        lat: latitude coordinate.
        lon: longitude coordinate.
        alert_api_id: unique sequence identifier for API.
        logger: logging instance for warnings.

    """
    script_path = resolve_annotation_script_path()
    if not script_path:
        logger.warning("Missing import_yolo_sequence.py script. Skipping API import.")
        return

    annotation_root = script_path.parents[4]
    env = build_annotation_env(annotation_root)

    cmd = [
        sys.executable,
        str(script_path),
        "--sequence-dir",
        str(sequence_dir),
        "--api-base",
        ANNOTATION_API_BASE,
        "--alert-api-id",
        str(alert_api_id),
        "--source-api",
        ANNOTATION_SOURCE_API,
        "--sequence-stage",
        ANNOTATION_SEQUENCE_STAGE,
        "--organisation-id",
        str(ANNOTATION_ORG_ID),
        "--organisation-name",
        ANNOTATION_ORG_NAME,
        "--camera-id",
        str(cam_id),
        "--camera-name",
        cam_name,
        "--azimuth", 
        str(azimuth),
        "--lat",
        str(lat),
        "--lon",
        str(lon),
        "--loglevel",
        "info",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    except Exception as exc:
        logger.warning("API import failed for %s: %s", sequence_dir, exc)
        return

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        details = stderr or stdout or "Unknown error"
        logger.warning("API import failed for %s: %s", sequence_dir, details)
