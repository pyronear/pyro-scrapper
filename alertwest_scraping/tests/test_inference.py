import os
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import List
from PIL import Image
from dataclasses import dataclass

import pytest

@dataclass
class ImageEntry:
    """Container for image path and timestamp."""

    path: Path
    ts: datetime

# Ensure repo root is on sys.path so tests can import alertwest_scraping
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def import_inference_with_fake_predictor(monkeypatch):
    """Load the utilities module with a lightweight fake Predictor to avoid heavy dependencies."""
    fake_predictor_module = types.SimpleNamespace(
        Predictor=type(
            "Predictor",
            (),
            {"__init__": lambda self: None, "predict": lambda self, img: 0.5},
        )
    )
    monkeypatch.setitem(sys.modules, "pyro_predictor", fake_predictor_module)

    import importlib

    return importlib.import_module("alertwest_scraping.utils_inference_annotation")


def test_parse_timestamp_from_filename(monkeypatch):
    mod = import_inference_with_fake_predictor(monkeypatch)

    ts = mod.parse_timestamp_from_filename(
        "11113_20260405_153253_161018_42.033887_-121.275861_Bryant_Mtn_2.jpg"
    )
    assert isinstance(ts, datetime)
    assert ts.year == 2026
    assert ts.month == 4
    assert ts.day == 5

    assert mod.parse_timestamp_from_filename("badname.jpg") is None


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

def test_find_sequences_consecutive(monkeypatch):
    mod = import_inference_with_fake_predictor(monkeypatch)

    base = datetime(2025, 1, 1, 12, 0, 0)
    entries = [
        mod.ImageEntry(Path("a.jpg"), base),
        mod.ImageEntry(Path("b.jpg"), base.replace(second=10)),
        mod.ImageEntry(Path("c.jpg"), base.replace(second=20)),
    ]

    sequences = find_sequences(entries, n=3, max_gap_seconds=15)
    assert len(sequences) == 1
    assert [e.path.name for e in sequences[0]] == ["a.jpg", "b.jpg", "c.jpg"]

    # Gap too large removes sequence
    assert find_sequences(entries, n=3, max_gap_seconds=5) == []

    # Non-overlapping behavior
    entries = [
        mod.ImageEntry(Path("a.jpg"), base),
        mod.ImageEntry(Path("b.jpg"), base.replace(second=10)),
        mod.ImageEntry(Path("c.jpg"), base.replace(second=20)),
        mod.ImageEntry(Path("d.jpg"), base.replace(second=30)),
        mod.ImageEntry(Path("e.jpg"), base.replace(second=40)),
        mod.ImageEntry(Path("f.jpg"), base.replace(second=50)),
    ]
    sequences = find_sequences(entries, n=3, max_gap_seconds=15)
    assert len(sequences) == 2
    assert [e.path.name for e in sequences[0]] == ["a.jpg", "b.jpg", "c.jpg"]
    assert [e.path.name for e in sequences[1]] == ["d.jpg", "e.jpg", "f.jpg"]


def test_iter_leaf_folders(monkeypatch, tmp_path):
    mod = import_inference_with_fake_predictor(monkeypatch)

    root = tmp_path / "images"
    (root / "CAM1" / "90").mkdir(parents=True)
    (root / "CAM2" / "180").mkdir(parents=True)

    leaves = list(mod.iter_leaf_folders(root))
    # Convert to POSIX paths for comparison to avoid OS path separator issues
    leaves_posix = sorted([p.as_posix() for p in leaves])
    expected_posix = sorted([
        (root / "CAM1" / "90").as_posix(),
        (root / "CAM2" / "180").as_posix()
    ])
    assert leaves_posix == expected_posix
