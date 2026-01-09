import pytest
import json
from io import BytesIO
from PIL import Image
from unittest.mock import patch, MagicMock

from scrappy_pyronear.spiders.alertwest_spider import AlertwestSpider
from scrappy_pyronear.items import PyronearItem
import scrappy_pyronear.spiders.alertwest_utils as utils_module

# Utility function to create a fake image
def create_fake_image(width=800, height=600):
    img = Image.new("RGB", (width, height), color="red")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()

# Fake response JSON
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
        "locs": {
            "key": {
                "id": "locId",
                "lat": "locLat",
                "lon": "locLon",
                "st": "locState",
                "lp": "locPrivate"
            },
            "data": [
                {"id": 21901, "lat": "20.607269", "lon": "-156.426950", "st": "HI", "lp": 0},
                {"id": 407, "lat": "38.588039", "lon": "-121.025063", "st": "CA", "lp": 0}
            ]
        }
    }
}

@pytest.fixture
def spider():
    s = AlertwestSpider()
    s.is_daytime_by_coords = lambda lat, lon: True
    return s

def test_alertwest_parse_with_image_size(monkeypatch, spider):
    import scrappy_pyronear.spiders.alertwest_spider as aw_module

    # Mock requests.get to return a fake image
    def fake_requests_get(url, timeout=5):
        if "lowres" in url:
            content = create_fake_image(width=320, height=240)  # Low-res
        else:
            content = create_fake_image(width=800, height=600)  # OK resolution
        resp = MagicMock()
        resp.content = content
        return resp

    monkeypatch.setattr(utils_module.requests, "get", fake_requests_get)

    # Mock save_cache to avoid writing to disk
    monkeypatch.setattr(aw_module, "save_cache", lambda *a, **kw: None)

    # Simulate parsing for "cycle 0"
    spider.cycle_number = 0
    from scrapy.http import TextResponse
    response = TextResponse(url="https://api.test/alertwest", body=json.dumps(sample_json), encoding="utf-8")

    items = list(spider.parse(response))

    # Verify that only valid cameras pass the filters
    ids = [i["id"] for i in items]
    assert "CAM001" in ids
    assert "CAM002" in ids
    assert "CAM003" not in ids  # Low-res filtered out
    assert "CAM004" not in ids  # Thermal filtered out
    assert "CAM005" not in ids  # Missing image filtered out

    # Verify that the item is a PyronearItem and contains expected fields
    for item in items:
        assert isinstance(item, PyronearItem)
        assert item["image_url"].startswith("https://img.cdn.prod.alertwest.com/data/img/")
        assert item["azimuth"] > 0
