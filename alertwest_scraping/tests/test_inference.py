import os
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest


# Ensure repo root is on sys.path so tests can import alertwest_scraping
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def import_inference_with_fake_engine(monkeypatch):
    """Load inference with a lightweight fake Engine to avoid heavy dependencies."""
    fake_core = types.SimpleNamespace(
        Engine=type(
            "Engine",
            (),
            {"__init__": lambda self: None, "predict": lambda self, img: 0.5},
        )
    )
    monkeypatch.setitem(sys.modules, "pyroengine", types.SimpleNamespace(core=fake_core))
    monkeypatch.setitem(sys.modules, "pyroengine.core", fake_core)

    import importlib

    return importlib.import_module("alertwest_scraping.inference")


def test_parse_timestamp_from_filename(monkeypatch):
    mod = import_inference_with_fake_engine(monkeypatch)

    ts = mod.parse_timestamp_from_filename("CAM1_20250101_120000_123456.jpg")
    assert isinstance(ts, datetime)
    assert ts.year == 2025

    assert mod.parse_timestamp_from_filename("badname.jpg") is None


def test_find_sequences_consecutive(monkeypatch):
    mod = import_inference_with_fake_engine(monkeypatch)

    base = datetime(2025, 1, 1, 12, 0, 0)
    entries = [
        mod.ImageEntry(Path("a.jpg"), base),
        mod.ImageEntry(Path("b.jpg"), base.replace(second=10)),
        mod.ImageEntry(Path("c.jpg"), base.replace(second=20)),
    ]

    sequences = mod.find_sequences(entries, n=3, max_gap_seconds=15)
    assert len(sequences) == 1
    assert [e.path.name for e in sequences[0]] == ["a.jpg", "b.jpg", "c.jpg"]

    # Gap too large removes sequence
    assert mod.find_sequences(entries, n=3, max_gap_seconds=5) == []

    # Non-overlapping behavior
    entries = [
        mod.ImageEntry(Path("a.jpg"), base),
        mod.ImageEntry(Path("b.jpg"), base.replace(second=10)),
        mod.ImageEntry(Path("c.jpg"), base.replace(second=20)),
        mod.ImageEntry(Path("d.jpg"), base.replace(second=30)),
        mod.ImageEntry(Path("e.jpg"), base.replace(second=40)),
        mod.ImageEntry(Path("f.jpg"), base.replace(second=50)),
    ]
    sequences = mod.find_sequences(entries, n=3, max_gap_seconds=15)
    assert len(sequences) == 2
    assert [e.path.name for e in sequences[0]] == ["a.jpg", "b.jpg", "c.jpg"]
    assert [e.path.name for e in sequences[1]] == ["d.jpg", "e.jpg", "f.jpg"]


def test_iter_leaf_folders(monkeypatch, tmp_path):
    mod = import_inference_with_fake_engine(monkeypatch)

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
