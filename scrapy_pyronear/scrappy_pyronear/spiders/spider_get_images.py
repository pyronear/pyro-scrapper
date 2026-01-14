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
    """Spider to download camera images from good_ids.json."""

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
        self.total_cams_to_get_image_of = 0


    def parse(self, response):
        """Load camera IDs from good_ids.json and yield requests."""
        if not self.good_ids_path.exists():
            self.logger.error(f"File good_ids.json not found: {self.good_ids_path}")
            return

        try:
            with open(self.good_ids_path, "r") as f:
                good_ids_data = json.load(f)
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in {self.good_ids_path}")
            return

        # extract the ids of good cameras
        camera_ids = good_ids_data.get("ids", [])
        self.total_cams_to_get_image_of = len(camera_ids)
            
        # Get the full camera json from the API and the keys
        data = json.loads(response.text)
        short_key_cams, _ = extract_keys(data)

        date_for_path = datetime.now().strftime("%Y/%m/%d")
        for cam in data:
            # Process only cameras in good_ids.json
            if cam.get(short_key_cams["camId"]) in camera_ids:
                yield PyronearItem(
                    id=cam.get(short_key_cams["camId"]),
                    name=cam.get(short_key_cams["camName"]),
                    azimuth=cam.get(short_key_cams["camAzimuth"]),
                    screenshot=cam.get(short_key_cams["camScreenshot"]),
                    offline=cam.get(short_key_cams["camOffline"]),
                    provider=cam.get(short_key_cams["providerName"]),
                )
