"""Spider to fetch and download images for valid camera IDs."""

import json
from pathlib import Path

import scrapy
from scrapy_core.items import PyronearItem

from .config import API_URL
from .spider_utils import extract_keys


class GetImagesSpider(scrapy.Spider):
    """Spider to download camera images from provided camera IDs."""

    name = "spider_get_images"
    custom_settings = {"ITEM_PIPELINES": {"scrapy_core.pipelines.GetImagesPipeline": 300}}
    start_urls = [API_URL]

    def __init__(self, *args, **kwargs):
        """Initialize spider."""
        super().__init__(*args, **kwargs)
        self.good_ids_path = Path(__file__).parent.parent.parent / "good_ids.json"

        # Accept camera_ids as parameter and convert from JSON string to list
        camera_ids = kwargs.get("camera_ids", [])
        if isinstance(camera_ids, str):
            camera_ids = json.loads(camera_ids)
        self.camera_ids = camera_ids
        self.camera_ids_set = set(camera_ids)
        self.total_cams_requested = len(self.camera_ids)
        self.total_cams_to_get_image_of = 0
        self.total_cams_missing_from_api = 0

    def parse(self, response):
        """Load camera IDs and yield requests for matching cameras."""
        # Get the full camera json from the API and the keys
        data = json.loads(response.text)
        short_key_cams, short_key_locs = extract_keys(data)
        data_cams = data.get("data", {}).get("cams", {}).get("data", [])
        data_locs = data.get("data", {}).get("locs", {}).get("data", [])
        cam_id_key = short_key_cams["camId"]

        # Construct a mapping of location_id to (lat, lon) for quick lookup
        locs_by_id = {
            loc.get(short_key_locs.get("locId")): (
                loc.get(short_key_locs.get("locLat")),
                loc.get(short_key_locs.get("locLon")),
            )
            for loc in data_locs
        }

        # Count against what is actually present in the current API payload.
        matched_cams = [cam for cam in data_cams if cam.get(cam_id_key) in self.camera_ids_set]
        self.total_cams_to_get_image_of = len(matched_cams)
        self.total_cams_missing_from_api = max(0, len(self.camera_ids_set) - self.total_cams_to_get_image_of)

        for cam in matched_cams:
            yield PyronearItem(
                id=cam.get(cam_id_key),
                name=cam.get(short_key_cams["camName"]),
                azimuth=cam.get(short_key_cams["camAzimuth"]),
                lat=locs_by_id.get(cam.get(short_key_cams["camLocation"]), (None, None))[0],
                lon=locs_by_id.get(cam.get(short_key_cams["camLocation"]), (None, None))[1],
                screenshot=cam.get(short_key_cams["camScreenshot"]),
                offline=cam.get(short_key_cams["camOffline"]),
                provider=cam.get(short_key_cams["providerName"]),
            )
