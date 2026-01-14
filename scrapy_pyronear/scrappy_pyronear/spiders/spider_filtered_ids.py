"""AlertWest spider for scraping camera images."""

import json
from datetime import datetime

import scrapy
from scrappy_pyronear.items import PyronearItem

from .alertwest_utils import (
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

    name = "alertwest_filtered_ids"
    custom_settings = {
        'ITEM_PIPELINES': {
            'app.FilteredIdsPipeline': 400
        }
    }
    start_urls = [API_URL]

    def parse(self, response):
        """Parse the API response and yield PyronearItems."""
        data = json.loads(response.text)
        self.total_cams = len(data)

        short_key_cams, _ = extract_keys(data)

        # Construct day path
        date_path = datetime.now().strftime("%Y/%m/%d")

        for cam in data:
            yield PyronearItem(
                id=cam.get(short_key_cams["camId"]),
                name=cam.get(short_key_cams["camName"]),
                azimuth=cam.get(short_key_cams["Azimuth"]),
                last_moved=int(cam.get(short_key_cams["camLastMoved"], 0)),
                image_url=(
                    f"https://img.cdn.prod.alertwest.com/data/img/"
                    f"{cam.get(short_key_cams['camId'])}/{date_path}/"
                    f"{cam.get(short_key_cams['Screenshot'])}"
                ),
                provider=cam.get(short_key_cams["providerName"]),
            )
        
