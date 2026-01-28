"""Spider to fetch all the camera and their infromations available on alertwest.com."""

import json

import scrapy
from scrapy_core.items import PyronearItem

from .config import API_URL
from .spider_utils import extract_keys

# Execute the code
# NORMAL : scrapy crawl alertwest
# WITH DEBUG : scrapy crawl alertwest -s LOG_LEVEL=DEBUG
# WITH RASPBERRY PARAMETERS : scrapy crawl alertwest -a n_raspberry=2 -a raspberry_id=0


class FilteredIdsSpider(scrapy.Spider):
    """Spider to scrape camera data from AlertWest API."""

    name = "spider_filtered_ids"
    custom_settings = {"ITEM_PIPELINES": {"scrapy_core.pipelines.FilteredIdsPipeline": 300}}
    start_urls = [API_URL]

    def __init__(self, *args, **kwargs):
        """Initialize spider."""
        super().__init__(*args, **kwargs)
        self.total_cams = 0

    def parse(self, response):
        """Parse the API response and yield PyronearItems."""
        data = json.loads(response.text)
        short_key_cams, _ = extract_keys(data)
        data_cams = data.get("data", {}).get("cams", {}).get("data", [])
        self.total_cams = len(data_cams)

        for cam in data_cams:
            yield PyronearItem(
                id=cam.get("id"),
                name=cam.get(short_key_cams["camName"]),
                azimuth=cam.get(short_key_cams["camAzimuth"]),
                screenshot=cam.get(short_key_cams["camScreenshot"]),
                offline=cam.get(short_key_cams["camOffline"]),
                provider=cam.get(short_key_cams["providerName"]),
            )
