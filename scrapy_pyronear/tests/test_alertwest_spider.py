"""Tests for the Alertwest spider."""

import json
import os
import sys

from scrapy.http import TextResponse

# Ensure project root is on sys.path so tests can import scrappy_pyronear
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrappy_pyronear.items import PyronearItem
from scrappy_pyronear.spiders.alertwest_spider import AlertwestSpider


def fake_response(json_data):
    """Create a fake Scrapy response containing JSON data."""
    body = json.dumps(json_data)
    return TextResponse(url="https://api.test/alertwest", body=body, encoding="utf-8")


def test_alertwest_spider_parse():
    """Ensure AlertwestSpider parses JSON into PyronearItems with image URLs."""
    spider = AlertwestSpider()

    sample_json = {
        "data": {
            "cams": {
                "key": {
                    "ato": "camAutoTargetOverride",
                    "p": "camAzimuth",
                    "t": "camElevation",
                    "z": "camZoom",
                    "af": "camAutoFocus",
                    "foc": "camFocus",
                    "br": "camBrightness",
                    "ptz": "camHasPTZ",
                    "id": "camId",
                    "pv": "camPrivate",
                    "lmt": "camLastMoved",
                    "lid": "camLocation",
                    "cn": "camName",
                    "hn": "camHostname",
                    "img": "camScreenshot",
                    "off": "camOffline",
                    "cl": "camLatency",
                    "isp": "camISP",
                    "typ": "camType",
                    "cc": "camClass",
                    "fov": "camViewWidth",
                    "sp": "camSponsor",
                    "co": "camCounty",
                    "st": "camState",
                    "pn": "camProviderName",
                    "pl": "camProviderLink",
                    "pi": "camProviderLogo",
                    "ps": "camProviderLogoSquare",
                    "tb": "camTourable",
                    "trg": "camTouring",
                    "tr": "camTour",
                },
                "data": [
                    {"p": 120, "lmt": "1600000", "id": "CAM001", "img": "image.jpg", "cn": "Camera 1"},
                    {"p": 45, "lmt": "1700000", "id": "CAM002", "img": "photo.png", "cn": "Camera 2"},
                ],
            }
        }
    }

    response = fake_response(sample_json)

    results = list(spider.parse(response))

    assert len(results) == 2

    item = results[0]
    assert isinstance(item, PyronearItem)
    assert item["id"] == "CAM001"
    assert item["name"] == "Camera 1"
    assert item["azimuth"] == 120
    assert "image.jpg" in item["image_url"]
