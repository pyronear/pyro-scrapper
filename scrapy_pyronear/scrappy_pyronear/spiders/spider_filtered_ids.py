"""Spider to fetch all the camera and their infromations available on alertwest.com."""

import json
from datetime import datetime

import scrapy
from scrappy_pyronear.items import PyronearItem

from .spider_utils import (
    extract_keys
)

from .config import (
    API_URL
)

# Execute the code
# NORMAL : scrapy crawl alertwest
# WITH DEBUG : scrapy crawl alertwest -s LOG_LEVEL=DEBUG
# WITH RASPBERRY PARAMETERS : scrapy crawl alertwest -a n_raspberry=2 -a raspberry_id=0

class FilteredIdsSpider(scrapy.Spider):
    """Spider to scrape camera data from AlertWest API."""

    name = "spider_filtered_ids"
    custom_settings = {
        'ITEM_PIPELINES': {
            'scrappy_pyronear.pipelines.FilteredIdsPipeline': 300
        }
    }
    start_urls = [API_URL]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_cams = 0
    

    def parse(self, response):
        """Parse the API response and yield PyronearItems."""
        data = json.loads(response.text)
        self.total_cams = len(data)

        short_key_cams, _ = extract_keys(data)

        for cam in data:
            yield PyronearItem(
                id=cam.get(short_key_cams["camId"]),
                name=cam.get(short_key_cams["camName"]),
                azimuth=cam.get(short_key_cams["camAzimuth"]),
                screenshot=cam.get(short_key_cams["camScreenshot"]),
                offline=cam.get(short_key_cams["camOffline"]),
                provider=cam.get(short_key_cams["providerName"]),
            )
        
