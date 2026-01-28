import os
import sys

# Ensure project root is on sys.path so tests can import scrapy_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrapy_core.spiders import spider_utils as utils


def test_extract_keys_maps_shortcuts(monkeypatch):
    """
    The spider utils must map human readable camera keys to the short API keys for
    both cameras and locations.
    """

    monkeypatch.setattr(
        utils,
        "INTERESTING_PROPERTIES",
        [
            "camAzimuth",
            "camScreenshot",
            "camName",
            "providerName",
            "locLat",
            "locLon",
        ],
    )

    sample = {
        "data": {
            "cams": {
                "key": {
                    "p": "camAzimuth",
                    "img": "camScreenshot",
                    "cn": "camName",
                    "pn": "providerName",
                },
                "data": [],
            },
            "locs": {
                "key": {
                    "lat": "locLat",
                    "lon": "locLon",
                },
                "data": [],
            },
        }
    }

    short_cams, short_locs = utils.extract_keys(sample)

    assert short_cams["camAzimuth"] == "p"
    assert short_cams["camScreenshot"] == "img"
    assert short_cams["camName"] == "cn"
    assert short_cams["providerName"] == "pn"
    assert short_locs["locLat"] == "lat"
    assert short_locs["locLon"] == "lon"