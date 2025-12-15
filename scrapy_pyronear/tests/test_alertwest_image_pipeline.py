"""Tests for the alertwest image pipeline."""

import os
import sys
import tempfile

import scrapy

# Ensure project root is on sys.path so tests can import scrappy_pyronear
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrappy_pyronear.items import PyronearItem
from scrappy_pyronear.pipelines import AlertwestImagePipeline


def test_get_media_requests_with_url(monkeypatch):
    """Ensure pipeline creates requests with correct metadata when URL exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = AlertwestImagePipeline(store_uri=f"file://{tmpdir}")
    spider = type("obj", (object,), {"total_cams": 1})

    pipeline.open_spider(spider)

    item = PyronearItem(id="CAM001", azimuth=120, last_moved=160000, image_url="http://example.com/img.jpg")

    reqs = list(pipeline.get_media_requests(item, info=type("obj", (object,), {"spider": spider})()))

    assert len(reqs) == 1
    req = reqs[0]
    assert isinstance(req, scrapy.Request)
    assert req.url == "http://example.com/img.jpg"
    assert req.meta["id"] == "CAM001"
    assert req.meta["azimuth"] == 120
    assert req.meta["last_moved"] == 160000


def test_file_path():
    """Ensure the pipeline builds the correct output path for an image."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = AlertwestImagePipeline(store_uri=f"file://{tmpdir}")

        item = PyronearItem(id="CAM1", azimuth=90, last_moved=123456)
        request = scrapy.Request(
            "http://example.com/img.jpg",
            meta={"id": item["id"], "azimuth": item["azimuth"], "last_moved": item["last_moved"]},
        )

        path = pipeline.file_path(request, item=item)
        assert path == os.path.join("CAM1", "90", "CAM1.jpg")
