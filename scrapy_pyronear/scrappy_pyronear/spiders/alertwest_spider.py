"""AlertWest spider for scraping camera images."""

import json
from datetime import datetime
from pathlib import Path

import scrapy
from scrappy_pyronear.items import PyronearItem

from .alertwest_utils import (
    extract_keys,
    clean_cameras_data,
    filter_night_cameras,
    split_json,
    save_cache,
)

# Execute the code
# NORMAL : scrapy crawl alertwest
# WITH DEBUG : scrapy crawl alertwest -s LOG_LEVEL=DEBUG
# WITH RASPBERRY PARAMETERS : scrapy crawl alertwest -a n_raspberry=2 -a raspberry_id=0


# INDIVIDUAL PROPERTIES TO EXTRACT FROM THE API RESPONSE
INTERESTING_PROPERTIES = [
    "Azimuth",
    "camLastMoved",
    "camId",
    "Screenshot",
    "camOffline",
    "camName",
    "providerName",
    "locLat",
    "locLon",
    "camLocation",
]
API_URL = "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc"
CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class AlertwestSpider(scrapy.Spider):
    """Spider to scrape camera data from AlertWest API."""

    name = "alertwest"
    start_urls = [API_URL]

    def __init__(self, n_raspberry=1, raspberry_id=0, cycle_number=0, cycle_refresh_json=50, *args, **kwargs):
        """Initialize the spider with Raspberry Pi distribution parameters."""
        super().__init__(*args, **kwargs)
        self.n_raspberry = int(n_raspberry)
        self.raspberry_id = int(raspberry_id)
        self.cycle_number = int(cycle_number)
        self.cycle_refresh_json = int(cycle_refresh_json)

    def items_from_data(self, final_data, short_key_cams):
        """Generate PyronearItem from final camera data."""
        date_path = datetime.now().strftime("%Y/%m/%d")
        self.total_relevant_cams = len(final_data)

        for cam in final_data:
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

    def process_from_api(self, data):
        short_key_cams, short_key_locs = extract_keys(data, INTERESTING_PROPERTIES)

        data_cams = data["data"]["cams"]["data"]
        data_locs = data["data"]["locs"]["data"]

        cleaned = clean_cameras_data(short_key_cams, data_cams)
        filtered = filter_night_cameras(cleaned, data_locs, short_key_locs)
        final = split_json(filtered, self.n_raspberry, self.raspberry_id)

        save_cache(short_key_cams, short_key_locs, data_locs)

        return final, short_key_cams
    
    def process_from_clean_cache(self):
        with open(CACHE_DIR / "alertwest_cleaned_json.json") as f:
            cleaned = json.load(f)

        with open(CACHE_DIR / "alertwest_keys.json") as f:
            keys = json.load(f)

        filtered = filter_night_cameras(
            cleaned,
            keys["locs"],
            keys["short_key_locs"],
        )

        final = split_json(filtered, self.n_raspberry, self.raspberry_id)

        return final, keys["short_key_cams"]
    
    def process_from_split_cache(self):
        with open(CACHE_DIR / f"alertwest_split_raspberry_{self.raspberry_id}.json") as f:
            cams = json.load(f)

        with open(CACHE_DIR / "alertwest_keys.json") as f:
            keys = json.load(f)

        return cams, keys["short_key_cams"]

    def parse(self, response):
        if self.cycle_number == 0:
            self.logger.info("🚀 First cycle – API → clean → filter → split")
            data = json.loads(response.text)
            final_data, short_key_cams = self.process_from_api(data)
            self.total_relevant_cams = len(final_data)

        elif self.cycle_number % self.cycle_refresh_json == 0:
            self.logger.info("🔄 Refresh from cleaned cache")
            final_data, short_key_cams = self.process_from_clean_cache()
            self.total_relevant_cams = len(final_data)

        else:
            self.logger.info("📦 Using cached split JSON")
            final_data, short_key_cams = self.process_from_split_cache()
            self.total_relevant_cams = len(final_data)

        yield from self.items_from_data(final_data, short_key_cams)
