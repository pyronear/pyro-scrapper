import json
import os
import sys

from scrapy.http import TextResponse

# Ensure package root is on sys.path so tests can import scrapy_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Ensure repo root is on sys.path so tests can import alertwest_scraping
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scrapy_core.items import PyronearItem
from scrapy_core.spiders.spider_filtered_ids import FilteredIdsSpider
from scrapy_core.spiders.spider_get_images import GetImagesSpider


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
                "tr": "camTour"
            },
            "data": [
                {"p": 120, "lmt": "1600000", "id": "CAM001", "img": "image.jpg", "cn": "Camera 1", "pn": "Provider A", "lid": 407},
                {"p": 45, "lmt": "1700000", "id": "CAM002", "img": "photo.png", "cn": "Camera 2", "pn": "Provider B", "lid": 21901},
                {"p": 47, "lmt": "1700000", "id": "CAM003", "img": "lowres.jpg", "cn": "Camera 3", "pn": "Provider C", "lid": 407},  # Low-res
                {"p": 48, "lmt": "1700000", "id": "CAM004", "img": "thermal.jpg", "cn": "Camera 4 Thermal", "pn": "Provider D", "lid": 407},  # Thermal
                {"p": 49, "lmt": "1700000", "id": "CAM005", "img": "", "cn": "Camera 5", "pn": "Provider E", "lid": 407},  # Missing image
            ]
        },
        "locs": {"key": {}, "data": []},
    }
}


def make_response(payload=None):
    body = json.dumps(payload or sample_json)
    return TextResponse(url="https://api.test/alertwest", body=body, encoding="utf-8")


def test_filtered_ids_spider_parses_all_cameras():
    spider = FilteredIdsSpider()

    items = list(spider.parse(make_response()))

    assert spider.total_cams == 5
    assert all(isinstance(item, PyronearItem) for item in items)
    assert [item["id"] for item in items] == ["CAM001", "CAM002", "CAM003", "CAM004", "CAM005"]
    assert items[0]["screenshot"] == "image.jpg"


def test_get_images_spider_filters_by_ids():
    spider = GetImagesSpider(camera_ids=["CAM001", "CAM003"])

    items = list(spider.parse(make_response()))

    ids = [item["id"] for item in items]
    assert ids == ["CAM001", "CAM003"]
    # Filter items that have non-empty screenshots
    assert all(item["screenshot"] for item in items if item["screenshot"])
