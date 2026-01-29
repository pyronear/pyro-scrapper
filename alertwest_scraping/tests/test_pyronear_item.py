import os
import sys

# Ensure project root is on sys.path so tests can import scrapy_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrapy_core.items import PyronearItem


def test_item_fields_and_defaults():
    """
    PyronearItem behaves like a Scrapy dict with the expected camera metadata fields.
    """

    item = PyronearItem(
        id="CAM01",
        name="Test Cam",
        azimuth=180,
        offline=0,
        screenshot="snap.jpg",
        provider="AlertWest",
    )

    assert item["id"] == "CAM01"
    assert item["name"] == "Test Cam"
    assert item["azimuth"] == 180
    assert item["offline"] == 0
    assert item["screenshot"] == "snap.jpg"
    assert item["provider"] == "AlertWest"