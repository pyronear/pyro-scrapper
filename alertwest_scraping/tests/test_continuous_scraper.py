import json
import os
import sys

import pytest

# Ensure project root is on sys.path so tests can import scrapy_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alertwest_scraping.continuous_workflow import ContinuousWorkflow


def test_run_inference_cleans_images(monkeypatch, tmp_path):
    """
    Night-time inference should invoke the inference pipeline and purge downloaded images afterwards.
    """

    wf = ContinuousWorkflow()
    wf.images_dir = tmp_path / "images"
    wf.annotations_dir = tmp_path / "annotations"
    wf.images_dir.mkdir(parents=True)
    (wf.images_dir / "dummy.jpg").write_text("data")

    called = {"inference": False}
    monkeypatch.setattr(
        "alertwest_scraping.continuous_workflow.run_inference_pipeline",
        lambda **kwargs: called.__setitem__("inference", True) or 0,
    )

    wf.run_inference()

    assert called["inference"] is True
    assert wf.inference_done is True
    assert not wf.images_dir.exists()


def test_split_camera_ids_even_distribution(monkeypatch, tmp_path):
    """
    Camera IDs must be evenly partitioned and persisted for each Raspberry Pi.
    """

    monkeypatch.setattr("alertwest_scraping.continuous_workflow.CACHE_DIR", tmp_path)

    wf = ContinuousWorkflow()
    wf.n_raspberry = 3
    wf.raspberry_id = 1

    camera_ids = [f"CAM{i}" for i in range(6)]
    subset = wf.split_camera_ids(camera_ids)

    assert subset == ["CAM1", "CAM4"]

    saved = []
    for rid in range(3):
        fpath = tmp_path / f"alertwest_split_raspberry_{rid}.json"
        assert fpath.exists()
        saved_ids = json.loads(fpath.read_text())
        saved.extend(saved_ids)

    assert sorted(saved) == camera_ids


def test_run_handles_night_then_day(monkeypatch, tmp_path):
    """
    The workflow should run inference at night, clean images at day start, split IDs, then scrape once.
    """

    monkeypatch.setattr("alertwest_scraping.continuous_workflow.CACHE_DIR", tmp_path)

    wf = ContinuousWorkflow(force_get_scrapping_ids=True)
    wf.images_dir = tmp_path / "images"
    wf.annotations_dir = tmp_path / "annotations"
    wf.good_ids_path = tmp_path / "good_ids.json"
    wf.images_dir.mkdir(parents=True)
    (wf.images_dir / "dummy.jpg").write_text("x")

    # is_night will return True once (night), then False for the day loop
    night_day = iter([True, False, False])
    wf.is_night = lambda: next(night_day, False)

    flags = {"inference": 0, "cleanup": 0, "cycle_ids": None}

    def fake_run_inference():
        flags["inference"] += 1
        wf.inference_done = True

    def fake_cleanup():
        flags["cleanup"] += 1
        if wf.images_dir.exists():
            import shutil

            shutil.rmtree(wf.images_dir)

    def fake_run_spider_filtered_ids():
        with open(wf.good_ids_path, "w") as f:
            json.dump({"ids": ["CAM0", "CAM1", "CAM2"]}, f)
        return True

    def fake_run_scraping_cycle(camera_ids):
        flags["cycle_ids"] = camera_ids
        wf.running = False

    wf.run_inference = fake_run_inference
    wf.cleanup_images = fake_cleanup
    wf.run_spider_filtered_ids = fake_run_spider_filtered_ids
    wf.run_scraping_cycle = fake_run_scraping_cycle

    wf.run()

    assert flags["inference"] == 1
    assert flags["cleanup"] >= 1
    assert flags["cycle_ids"] == ["CAM0", "CAM2"]

    # Split files should cover all IDs
    assert (tmp_path / "alertwest_split_raspberry_0.json").exists()
    assert (tmp_path / "alertwest_split_raspberry_1.json").exists()
    assert json.loads((tmp_path / "alertwest_split_raspberry_0.json").read_text()) == ["CAM0", "CAM2"]
    assert json.loads((tmp_path / "alertwest_split_raspberry_1.json").read_text()) == ["CAM1"]
