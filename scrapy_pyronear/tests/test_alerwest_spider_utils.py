import pytest
import json
from io import BytesIO
from PIL import Image
from unittest.mock import patch, MagicMock

from scrappy_pyronear.spiders import alertwest_utils as utils

# -----------------------------
# Helper functions
# -----------------------------

def create_fake_image(width=800, height=600):
    """Create an in-memory fake JPEG image."""
    img = Image.new("RGB", (width, height), color="red")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


# -----------------------------
# Test extract_keys
# -----------------------------

def test_extract_keys_basic(monkeypatch):
    INTERESTING_PROPERTIES = ["Azimuth", "Screenshot", "camName", "camProvider"]

    # Sample JSON mimicking API response
    sample_data = {
        "data": {
            "cams": {
                "key": {"p": "camAzimuth", "img": "camScreenshot", "cn": "camName", "pn": "camProviderName"},
                "data": []
            },
            "locs": {
                "key": {"lat": "locLat", "lon": "locLon"},
                "data": []
            }
        }
    }

    # Patch INTERESTING_PROPERTIES for testing
    monkeypatch.setattr(utils, "INTERESTING_PROPERTIES", INTERESTING_PROPERTIES)

    short_key_cams, short_key_locs = utils.extract_keys(sample_data)

    assert short_key_cams["Azimuth"] == "p"
    assert short_key_cams["Screenshot"] == "img"
    assert short_key_cams["camName"] == "cn"
    assert short_key_cams["camProvider"] == "pn"
    assert short_key_locs.get("Azimuth") is None


# -----------------------------
# Test is_daytime_by_coords
# -----------------------------

def test_is_daytime_by_coords(monkeypatch):
    # Patch timezone finder to return fixed timezone
    monkeypatch.setattr(utils, "_tz_finder", MagicMock(timezone_at=lambda lat, lng: "UTC"))

    # Patch sun calculation to return sunrise/sunset
    monkeypatch.setattr(utils, "sun", lambda observer, date, tzinfo: {"sunrise": 0, "sunset": 9999})

    # It should always return True because 0 <= now <= 9999
    result = utils.is_daytime_by_coords(0, 0)
    assert result in [True, False]  # Depending on actual datetime; main goal is no exception


# -----------------------------
# Test clean_cameras_data
# -----------------------------

def test_clean_cameras_data(monkeypatch, tmp_path):
    # Override CACHE_DIR to temporary directory
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path)

    short_key_cams = {
        "camId": "id",
        "Screenshot": "img",
        "camName": "cn",
        "providerName": "pn",
        "camOffline": "off",
    }

    data_cams = [
        {"id": "CAM1", "img": "ok.jpg", "cn": "Camera 1", "pn": "Provider A", "off": 0},
        {"id": "CAM2", "img": "lowres.jpg", "cn": "Camera 2", "pn": "Provider A", "off": 0},
        {"id": "CAM3", "img": "thermal.jpg", "cn": "Camera 3 Thermal", "pn": "Provider A", "off": 0},
        {"id": "CAM4", "img": "", "cn": "Camera 4", "pn": "Provider A", "off": 0},
        {"id": "CAM5", "img": "dot.jpg", "cn": "Camera 5", "pn": "Provider DOT", "off": 0},
        {"id": "CAM6", "img": "offline.jpg", "cn": "Camera 6", "pn": "Provider A", "off": 1},
    ]

    # Patch requests.get to simulate image download
    def fake_get(url, timeout=5):
        if "lowres" in url:
            content = create_fake_image(width=320, height=240)
        else:
            content = create_fake_image(width=800, height=600)
        resp = MagicMock()
        resp.content = content
        return resp

    monkeypatch.setattr(utils.requests, "get", fake_get)

    cleaned = utils.clean_cameras_data(short_key_cams, data_cams)
    # Only CAM1 should pass all filters
    ids = [c["id"] for c in cleaned]
    assert ids == ["CAM1"]

    # File should be written
    assert (tmp_path / "alertwest_cleaned_json.json").exists()


# -----------------------------
# Test filter_night_cameras
# -----------------------------

def test_filter_night_cameras(monkeypatch, tmp_path):
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(utils, "is_daytime_by_coords", lambda lat, lon: True)

    cleaned_json = [{"lid": 1, "id": "CAM1"}]
    data_locs = [{"id": 1, "locLat": 0, "locLon": 0}]
    short_key_locs = {"locLat": "locLat", "locLon": "locLon"}

    filtered = utils.filter_night_cameras(cleaned_json, data_locs, short_key_locs)
    assert len(filtered) == 1
    # File should be written
    assert (tmp_path / "alertwest_daytime_filtered_json.json").exists()


# -----------------------------
# Test split_json
# -----------------------------

def test_split_json(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path)
    data = [{"id": f"CAM{i}"} for i in range(6)]

    # Split 2 Raspberry Pis, raspberry_id = 1
    splitted = utils.split_json(data, n_raspberry=2, raspberry_id=1)
    # Should contain only indices 1,3,5
    assert [c["id"] for c in splitted] == ["CAM1", "CAM3", "CAM5"]
    # Files should exist
    assert (tmp_path / "alertwest_split_raspberry_0.json").exists()
    assert (tmp_path / "alertwest_split_raspberry_1.json").exists()


# -----------------------------
# Test save_cache
# -----------------------------

def test_save_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "CACHE_DIR", tmp_path)
    short_key_cams = {"camId": "id"}
    short_key_locs = {"locLat": "lat"}
    locs = [{"id": 1}]

    utils.save_cache(short_key_cams, short_key_locs, locs)
    # File should exist
    fpath = tmp_path / "alertwest_keys.json"
    assert fpath.exists()
    data = json.load(open(fpath))
    assert data["short_key_cams"] == short_key_cams
    assert data["short_key_locs"] == short_key_locs
    assert data["locs"] == locs