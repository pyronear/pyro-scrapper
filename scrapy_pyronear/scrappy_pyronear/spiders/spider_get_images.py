"""Spider to fetch and download images for valid camera IDs."""

import json
from pathlib import Path
from datetime import datetime
import scrapy
from scrappy_pyronear.items import PyronearItem

from .spider_utils import (
    extract_keys
)
from .config import (
    API_URL
)

class GetImagesSpider(scrapy.Spider):
    """Spider to download camera images from provided camera IDs."""

    name = "spider_get_images"
    custom_settings = {
        'ITEM_PIPELINES': {
            'scrappy_pyronear.pipelines.GetImagesPipeline': 300
        }
    }
    start_urls = [API_URL]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.good_ids_path = Path(__file__).parent.parent.parent / "good_ids.json"
        
        # Accept camera_ids as parameter and convert from JSON string to list
        camera_ids = kwargs.get("camera_ids", [])
        if isinstance(camera_ids, str):
            camera_ids = json.loads(camera_ids)
        self.camera_ids = camera_ids
        self.total_cams_to_get_image_of = len(self.camera_ids)

    def parse(self, response):
        """Load camera IDs and yield requests for matching cameras."""

        # Get the full camera json from the API and the keys
        data = json.loads(response.text)
        short_key_cams, _ = extract_keys(data)
        data_cams = data.get("data", {}).get("cams", {}).get("data", [])


        for cam in data_cams:
            # Process only cameras in the camera_ids list
            if cam.get(short_key_cams["camId"]) in self.camera_ids:
                yield PyronearItem(
                    id=cam.get(short_key_cams["camId"]),
                    name=cam.get(short_key_cams["camName"]),
                    azimuth=cam.get(short_key_cams["camAzimuth"]),
                    screenshot=cam.get(short_key_cams["camScreenshot"]),
                    offline=cam.get(short_key_cams["camOffline"]),
                    provider=cam.get(short_key_cams["providerName"]),
                )
