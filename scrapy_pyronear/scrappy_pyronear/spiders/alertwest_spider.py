"""AlertWest spider for scraping camera images."""

import json
from datetime import datetime

import scrapy
from scrappy_pyronear.items import PyronearItem

from pathlib import Path
from scrapy.http import HtmlResponse

# Execute the code
# NORMAL : scrapy crawl alertwest
# WITH DEBUG : scrapy crawl alertwest -s LOG_LEVEL=DEBUG
# WITH RASPBERRY PARAMETERS : scrapy crawl alertwest -a n_raspberry=2 -a raspberry_id=0


# INDIVIDUAL PROPERTIES TO EXTRACT FROM THE API RESPONSE
INTERESTING_PROPERTIES = ["Azimuth", "camLastMoved", "camId", "Screenshot", "camOffline", "camName", "providerName"]
API_URL = "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc"
CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class AlertwestSpider(scrapy.Spider):
    """Spider to scrape camera data from AlertWest API."""

    name = "alertwest"
    start_urls = [API_URL]

    def __init__(self, n_raspberry=1, raspberry_id=0, cycle_number=0, *args, **kwargs):
        """Initialize the spider with Raspberry Pi distribution parameters."""
        super().__init__(*args, **kwargs)
        self.n_raspberry = int(n_raspberry)
        self.raspberry_id = int(raspberry_id)
        self.cycle_number = int(cycle_number)

        self.thermal_cams_ = 0
        self.dot_cams_ = 0
        self.missing_params_ = 0

    def clean_cameras_data(self, short_key, data_cams):
        """Clean the JSON data by keeping only relevant items."""
        cleaned_file_json = CACHE_DIR / f"alertwest_cleaned_json.json"
        cleaned_json = []

        for cam in data_cams:
            cam_id = cam.get(short_key["camId"])
            img_name = cam.get(short_key["Screenshot"])
            cam_name = (cam.get(short_key["camName"]) or "").lower()
            provider = (cam.get(short_key["providerName"]) or "").lower()

            if "thermal" in cam_name:
                self.thermal_cams_ += 1
                continue
            if "dot" in provider:
                self.dot_cams_ += 1
                continue
            if not cam_id or not img_name:
                self.missing_params_ += 1
                continue

            cleaned_json.append(cam)

        print(f"Skipped {self.thermal_cams_} thermal cameras among {len(data_cams)} total cameras.")
        print(f"Skipped {self.dot_cams_} DOT cameras among {len(data_cams)} total cameras.")
        print(
            f"Miss a parameter in the json to construct URL for {self.missing_params_} cameras among {len(data_cams)} total cameras."
        )
        print(f"Total relevant cameras after cleaning: {len(cleaned_json)}")

        # Stocker le JSON nettoyé
        with open(cleaned_file_json, "w") as f:
            json.dump(cleaned_json, f)

        return cleaned_json

    def split_json(self, data):
        """Split the JSON data for distributed scraping across multiple Raspberry Pi."""

        splitted_for_me = []

        for rid in range(self.n_raspberry):
            subset = [cam for idx, cam in enumerate(data) if idx % self.n_raspberry == rid]
            file_splitted_json = CACHE_DIR / f"alertwest_split_raspberry_{rid}.json"
            with open(file_splitted_json, "w") as f:
                json.dump(subset, f)
            if rid == self.raspberry_id:
                splitted_for_me = subset

        return splitted_for_me

    def items_from_data(self, final_data, short_key):
        """Generate PyronearItem from final_data and short_key."""
        self.total_relevant_cams = len(final_data)
        date_path = datetime.now().strftime("%Y/%m/%d")

        for cam in final_data:
            yield PyronearItem(
                id=cam.get(short_key["camId"]),
                name=cam.get(short_key["camName"]),
                azimuth=cam.get(short_key["Azimuth"]),
                last_moved=int(cam.get(short_key["camLastMoved"], "0")),
                image_url=f"https://img.cdn.prod.alertwest.com/data/img/{cam.get(short_key['camId'])}/{date_path}/{cam.get(short_key['Screenshot'])}",
                provider=cam.get(short_key["providerName"]),
            )


    def start_requests(self):
        """Decide whether to fetch API or use cached JSON."""
        cache_file = CACHE_DIR / f"alertwest_cache_raspberry_{self.raspberry_id}.json"
        refresh = self.cycle_number % 1000 == 0 or not cache_file.exists()

        if refresh:
            self.logger.info("🔄 Refreshing AlertWest JSON from API")
            yield scrapy.Request(API_URL, callback=self.parse)
        else:
            self.logger.info("📦 Using cached AlertWest JSON")
            # Charger le cache directement sans écraser
            with open(cache_file, "r") as f:
                payload = json.load(f)
            final_data = payload["cams"]
            short_key = payload["short_key"]
            yield from self.items_from_data(final_data, short_key)


    def parse(self, response):
        """Parse the API response, clean & split data, cache it, and yield items."""
        data = json.loads(response.text)
        key_list = data.get("data", {}).get("cams", {}).get("key", {})
        data_cams = data.get("data", {}).get("cams", {}).get("data", [])

        # Map properties to short keys
        short_key = {
            prop: short
            for prop in INTERESTING_PROPERTIES
            for short, longname in key_list.items()
            if isinstance(longname, str) and prop.lower() in longname.lower()
        }

        # Clean and split data
        cleaned_data = self.clean_cameras_data(short_key, data_cams)
        final_data = self.split_json(cleaned_data)

        # Cache for this raspberry
        cache_file = CACHE_DIR / f"alertwest_cache_raspberry_{self.raspberry_id}.json"
        with open(cache_file, "w") as f:
            json.dump({"short_key": short_key, "cams": final_data}, f)

        yield from self.items_from_data(final_data, short_key)
