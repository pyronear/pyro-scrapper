import os
import sys
import types
from datetime import datetime
from pathlib import Path

# Ensure repo root is on sys.path so tests can import alertwest_scraping
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from alertwest_scraping.send_annotation_api import import_sequence_via_annotation_api
from alertwest_scraping.inference import ImageEntry


def test_import_sequence_via_annotation_api_uses_credentials(monkeypatch, tmp_path):
    calls = {
        "auth": 0,
        "create_sequence": 0,
        "create_detection": 0,
        "create_sequence_annotation": 0,
    }

    def fake_get_auth_token(base_url, username, password):
        assert username == "user"
        assert password == "pass"
        calls["auth"] += 1
        return "token"

    def fake_create_sequence(base_url, token, payload):
        calls["create_sequence"] += 1
        assert payload["is_wildfire_alertapi"] in {"wildfire_smoke", "other_smoke", "other"}
        return {"id": 123}

    def fake_create_detection(base_url, token, payload, image_bytes, filename):
        calls["create_detection"] += 1
        assert payload["sequence_id"] == 123
        assert isinstance(image_bytes, (bytes, bytearray))
        return {"id": 900 + calls["create_detection"]}

    def fake_create_sequence_annotation(base_url, token, payload):
        calls["create_sequence_annotation"] += 1
        assert payload["sequence_id"] == 123
        return {"id": 456}

    fake_annotation_api = types.SimpleNamespace(
        get_auth_token=fake_get_auth_token,
        create_sequence=fake_create_sequence,
        create_detection=fake_create_detection,
        create_sequence_annotation=fake_create_sequence_annotation,
    )

    fake_shared = types.SimpleNamespace(
        get_annotation_credentials=lambda base_url: ("user", "pass")
    )

    monkeypatch.setitem(sys.modules, "app", types.SimpleNamespace(clients=types.SimpleNamespace(annotation_api=fake_annotation_api)))
    monkeypatch.setitem(sys.modules, "app.clients", types.SimpleNamespace(annotation_api=fake_annotation_api))
    monkeypatch.setitem(sys.modules, "app.clients.annotation_api", fake_annotation_api)
    monkeypatch.setitem(
        sys.modules,
        "scripts.data_transfer.ingestion.platform.shared",
        fake_shared,
    )

    monkeypatch.setattr(
        "alertwest_scraping.send_annotation_api.ensure_annotation_api_importable",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "alertwest_scraping.send_annotation_api.load_annotation_env",
        lambda *args, **kwargs: None,
    )

    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    img1.write_bytes(b"data1")
    img2.write_bytes(b"data2")

    seq = [
        ImageEntry(img1, datetime(2025, 3, 4, 12, 0, 0)),
        ImageEntry(img2, datetime(2025, 3, 4, 12, 0, 20)),
    ]

    labels_by_path = {
        img1: [(0, 0.5, 0.5, 0.2, 0.2)],
        img2: [(0, 0.4, 0.4, 0.3, 0.3)],
    }

    import_sequence_via_annotation_api(
        seq,
        cam_id="123",
        cam_name="cam",
        azimuth=90,
        lat=43.6,
        lon=1.44,
        alert_api_id=111,
        labels_by_path=labels_by_path,
        logger=types.SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    assert calls["auth"] == 1
    assert calls["create_sequence"] == 1
    assert calls["create_detection"] == 2
    assert calls["create_sequence_annotation"] == 1
