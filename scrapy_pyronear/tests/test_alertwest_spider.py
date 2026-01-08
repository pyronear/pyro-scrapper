import os
import sys
# Ensure project root is on sys.path so tests can import scrappy_pyronear
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import types
from zoneinfo import ZoneInfo
from scrapy.http import TextResponse
from scrappy_pyronear.spiders.alertwest_spider import AlertwestSpider
import scrappy_pyronear.spiders.alertwest_spider as aw_module
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
    # Ensure daytime filtering doesn't exclude test items
    spider.is_daytime_by_coords = lambda lat, lon: True

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
                    {"p": 46, "lmt": "1700000", "id": "CAM002", "img": "photo.png", "cn": "Camera 3", "pn": "Provider B DOT", "lid": 407},
                    {"p": 47, "lmt": "1700000", "id": "CAM002", "img": "photo.png", "cn": "Camera 4 Thermal", "pn": "Provider B", "lid": 407},
                    {"p": 47, "lmt": "1700000", "id": "CAM002", "img": "", "cn": "Camera 4 Thermal", "pn": "Provider B", "lid": 407}
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

    response = fake_response(sample_json)

    results = list(spider.parse(response))

    assert len(results) == 2

    item = results[0]
    assert isinstance(item, PyronearItem)
    assert item["id"] == "CAM001"
    assert item["name"] == "Camera 1"
    assert item["azimuth"] == 120
    assert "image.jpg" in item["image_url"]


def test_alertwest_spider_filter_counts():
    """
    Verify filtering counts (night + offline + thermal + DOT) and resulting items
    based on ground truth using local daytime determination.
    """
    spider = AlertwestSpider()

    # Sample JSON with cams and locs; cams reference locs via 'lid'
    sample_json = {
        "data": {
            "cams": {
                "key": {
                    "p": "camAzimuth",
                    "lmt": "camLastMoved",
                    "id": "camId",
                    "img": "camScreenshot",
                    "cn": "camName",
                    "pn": "camProviderName",
                    "off": "camOffline",
                    "lid": "camLocation",
                },
                "data": [
                    {"p": 120, "lmt": "1600000", "id": "CAM001", "img": "image.jpg", "cn": "Camera 1", "pn": "Provider A", "off": 0, "lid": 407},
                    {"p": 45,  "lmt": "1700000", "id": "CAM002", "img": "photo.png", "cn": "Camera 2", "pn": "Provider B DOT", "off": 0, "lid": 407},
                    {"p": 47,  "lmt": "1700000", "id": "CAM003", "img": "thermal.png", "cn": "Camera 3 Thermal", "pn": "Provider A", "off": 0, "lid": 407},
                    {"p": 30,  "lmt": "1700000", "id": "CAM004", "img": "offline.png", "cn": "Camera 4", "pn": "Provider A", "off": 1, "lid": 407},
                    {"p": 60,  "lmt": "1700000", "id": "CAM005", "img": "night.png",   "cn": "Camera 5", "pn": "Provider A", "off": 0, "lid": 21901},
                ],
            },
            "locs": {
                "key": {
                    "id": "locId",
                    "lat": "locLat",
                    "lon": "locLon",
                    "st": "locState",
                    "lp": "locPrivate",
                },
                "data": [
                    {"id": 21901, "lat": "20.607269", "lon": "-156.426950", "st": "HI", "lp": 0},  # will be night
                    {"id": 407,   "lat": "38.588039", "lon": "-121.025063", "st": "CA", "lp": 0},   # will be day
                ],
            },
        }
    }

    # Mock is_daytime_by_coords: return False for HI coords (night), True for CA coords (day)
    def mock_is_daytime(lat, lon):
        try:
            return not (abs(float(lat) - 20.607269) < 1e-6 and abs(float(lon) + 156.426950) < 1e-6)
        except Exception:
            return True

    spider.is_daytime_by_coords = mock_is_daytime

    response = fake_response(sample_json)
    results = list(spider.parse(response))

    # Ground truth counts
    assert spider.thermal_cams_ == 1
    assert spider.dot_cams_ == 1
    assert spider.offline_cams_ == 1
    assert spider.night_cams_ == 1

    # Expected resulting items: only CAM001 (daytime, not dot, not thermal, not offline)
    assert len(results) == 1
    assert isinstance(results[0], PyronearItem)
    assert results[0]["id"] == "CAM001"


def test_is_daytime_by_coords_astral_day(monkeypatch):
    """Confirm astral-based daytime detection returns True at midday local time."""
    spider = AlertwestSpider()

    # Stub timezonefinder to return America/Los_Angeles
    class StubTZ:
        def timezone_at(self, lat, lng):
            return "America/Los_Angeles"

    spider._tz_finder = StubTZ()

    # Monkeypatch module datetime.now to return 12:00 local time
    noon_la = aw_module.datetime(2026, 6, 21, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    monkeypatch.setattr(aw_module, "datetime", types.SimpleNamespace(now=lambda tz: noon_la))

    # Los Angeles coords
    assert spider.is_daytime_by_coords("34.0522", "-118.2437") is True


def test_is_daytime_by_coords_astral_night(monkeypatch):
    """Confirm astral-based daytime detection returns False at night local time."""
    spider = AlertwestSpider()

    # Stub timezonefinder to return America/Los_Angeles
    class StubTZ:
        def timezone_at(self, lat, lng):
            return "America/Los_Angeles"

    spider._tz_finder = StubTZ()

    # Monkeypatch module datetime.now to return 02:00 local time
    night_la = aw_module.datetime(2026, 1, 7, 2, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    monkeypatch.setattr(aw_module, "datetime", types.SimpleNamespace(now=lambda tz: night_la))

    # Los Angeles coords
    assert spider.is_daytime_by_coords("34.0522", "-118.2437") is False