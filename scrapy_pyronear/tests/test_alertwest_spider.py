import os
import sys
# Ensure project root is on sys.path so tests can import scrappy_pyronear
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from scrapy.http import TextResponse
from scrappy_pyronear.spiders.alertwest_spider import AlertwestSpider
from scrappy_pyronear.items import PyronearItem

def fake_response(json_data):
    '''
    Creates a fake Scrappy response containing json data.
    '''
    body = json.dumps(json_data)
    return TextResponse(
        url="https://api.test/alertwest",
        body=body,
        encoding="utf-8"
    )

def test_alertwest_spider_parse():
    '''
    Checks that the AlertwestSpider correctly parses a sample JSON response and creates a valid PyronearItem and a valid image url.
    '''
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
                        "tr": "camTour"
                    }, 
                "data": [
                    {"p": 120, "lmt": "1600000", "id": "CAM001", "img": "image.jpg", "cn": "Camera 1"},
                    {"p": 45, "lmt": "1700000", "id": "CAM002", "img": "photo.png", "cn": "Camera 2"},
                ]
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