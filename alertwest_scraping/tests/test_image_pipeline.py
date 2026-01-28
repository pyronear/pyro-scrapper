import os
import sys
import tempfile
from datetime import datetime

import scrapy

# Ensure project root is on sys.path so tests can import scrapy_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrapy_core.items import PyronearItem
from scrapy_core.pipelines import FilteredIdsPipeline, GetImagesPipeline


def test_get_media_requests_builds_request(monkeypatch):
    """
    The image pipeline must generate a request with camera metadata and a timestamped identifier.
    """

    fixed_now = datetime(2025, 1, 1, 12, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D401 - deterministic clock for the test
            return fixed_now

    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GetImagesPipeline(store_uri=f"file://{tmpdir}")
        # Provide a minimal crawler stub to avoid touching pipeline internals
        spider = type("Spider", (), {"camera_ids": ["CAM001"], "crawler": type("Crawler", (), {})()})()
        info = type("Info", (), {"spider": spider})()

        pipeline.open_spider(spider)
        monkeypatch.setattr("scrapy_core.pipelines.datetime", FrozenDateTime)

        item = PyronearItem(id="CAM001", azimuth=90, screenshot="img.jpg")
        requests = list(pipeline.get_media_requests(item, info=info))

        assert len(requests) == 1
        req = requests[0]
        assert isinstance(req, scrapy.Request)
        assert "img.jpg" in req.url
        assert req.meta["id"] == "CAM001"
        assert req.meta["azimuth"] == 90
        assert isinstance(req.meta["scraped_at"], str)
        assert len(req.meta["scraped_at"]) > 0


def test_file_path_handles_missing_azimuth():
    """
    file_path should fall back to "unknown" when azimuth is missing from the item.
    """

    pipeline = GetImagesPipeline(store_uri="file://tmp")
    item = PyronearItem(id="CAM1", azimuth=None, screenshot="img.jpg")
    request = scrapy.Request(
        "http://example.com/img.jpg",
        meta={"id": item["id"], "scraped_at": "20250101_120000_123456"},
    )

    path = pipeline.file_path(request, item=item)
    assert path == os.path.join("CAM1", "unknown", "CAM1_20250101_120000_123456.jpg")


def test_filtered_ids_pipeline_writes_good_ids(tmp_path):
    """
    When the filtering pipeline closes it must persist the collected IDs to disk.
    """

    pipeline = FilteredIdsPipeline()
    pipeline.output_file = tmp_path / "good_ids.json"
    pipeline.good_ids = {"ids": ["CAM1", "CAM2"]}
    pipeline.stats = {
        "thermal": 0,
        "dot": 0,
        "offline": 0,
        "missing_informations": 0,
        "low_res": 0,
        "total": 2,
    }
    # Ensure attribute exists without touching pipeline implementation
    pipeline.progress_bar = None

    pipeline.close_spider(spider=object())

    assert pipeline.output_file.exists()
    assert pipeline.output_file.read_text().strip().startswith("{")


# def test_filtered_ids_pipeline_processes_valid_items(tmp_path):
#     """Test that FilteredIdsPipeline processes valid items correctly."""
#     pipeline = FilteredIdsPipeline()
#     pipeline.output_file = tmp_path / "good_ids.json"

#     spider = type("Spider", (), {"logger": type("Logger", (), {"info": lambda x: None})()})()
#     pipeline.open_spider(spider)

#     item = PyronearItem(id="CAM001", name="Test Camera", offline=0, screenshot="test.jpg")
#     result = pipeline.process_item(item, spider)

#     assert result["id"] == "CAM001"
#     assert "CAM001" in [cam["id"] for cam in pipeline.good_ids["ids"]]


# def test_get_images_pipeline_saves_image_to_disk(tmp_path):
#     """Test that GetImagesPipeline saves images to disk with correct naming."""
#     pipeline = GetImagesPipeline(store_uri=f"file://{tmp_path}")
#     spider = type("Spider", (), {"camera_ids": ["CAM001"]})()
#     pipeline.open_spider(spider)

#     # Simulate file_path and item_completed
#     request = scrapy.Request(
#         "http://example.com/image.jpg",
#         meta={"id": "CAM001", "azimuth": 90, "scraped_at": "20250101_120000_123456"},
#     )
#     item = PyronearItem(id="CAM001", azimuth=90, screenshot="image.jpg")

#     path = pipeline.file_path(request, item=item)
#     assert "CAM001" in path
#     assert "20250101_120000_123456" in path


# def test_get_images_pipeline_creates_directory_structure(tmp_path):
#     """Test that GetImagesPipeline creates proper directory structure."""
#     pipeline = GetImagesPipeline(store_uri=f"file://{tmp_path}")
#     spider = type("Spider", (), {"camera_ids": ["CAM001"]})()

#     pipeline.open_spider(spider)

#     # Verify store_uri directory exists
#     assert (tmp_path / "full").exists()
#     assert (tmp_path / "thumbs").exists()