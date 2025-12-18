"""AlertWest spider for scraping camera images."""

import json
from datetime import datetime

import scrapy
from scrappy_pyronear.items import PyronearItem

# Execute the code
# NORMAL : scrapy crawl alertwest
# WITH DEBUG : scrapy crawl alertwest -s LOG_LEVEL=DEBUG
# WITH RASPBERRY PARAMETERS : scrapy crawl alertwest -a n_raspberry=2 -a raspberry_id=0


# INDIVIDUAL PROPERTIES TO EXTRACT FROM THE API RESPONSE
INTERESTING_PROPERTIES = ["Azimuth", "camLastMoved", "camId", "Screenshot", "camOffline", "camName", "providerName"]
API_URL = "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc"


class AlertwestSpider(scrapy.Spider):
    """Spider to scrape camera data from AlertWest API."""

    name = "alertwest"
    start_urls = [API_URL]

    def __init__(self, n_raspberry=1, raspberry_id=0, *args, **kwargs):
        """Initialize the spider with Raspberry Pi distribution parameters."""
        super().__init__(*args, **kwargs)
        self.n_raspberry = int(n_raspberry)
        self.raspberry_id = int(raspberry_id)

    def clean_cameras_data(self, short_key, data_cams):
        """Clean the JSON data by keeping only relevant items."""
        cleaned_json = []
        thermal_cams = 0
        dot_cams = 0
        missing_params = 0

        # Iterate over cameras and filter out unwanted ones
        for cam in data_cams:
            cam_id = cam.get(short_key["camId"], None)
            img_name = cam.get(short_key["Screenshot"], None)
            cam_name = cam.get(short_key["camName"], None)
            provider = cam.get(short_key["providerName"], None)

            if "thermal" in cam_name.lower():
                thermal_cams += 1
                continue
            if "dot" in provider.lower():
                dot_cams += 1
                continue
            if not cam_id or not img_name:
                missing_params += 1
                continue

            # Add item to cleaned json
            cleaned_json.append(cam)

        return cleaned_json, thermal_cams, dot_cams, missing_params

    def split_json(self, data):
        """Split the JSON data for distributed scraping across multiple Raspberry Pi."""
        splitted_json = []

        # Iterate over cameras and keep only those assigned to this Raspberry Pi
        for index, cam in enumerate(data):
            if index % self.n_raspberry == self.raspberry_id:
                splitted_json.append(cam)

        return splitted_json

    # automatically called when the spider is opened
    def parse(self, response):
        """Parse the API response and extract camera items."""
        # Fetch the JSON data
        data = json.loads(response.text)

        key_list = data.get("data", {}).get("cams", {}).get("key", {})
        data_cams = data.get("data", {}).get("cams", {}).get("data", [])

        # Construct a mapping from property to short key ( ex: "Azimuth" -> "p" )
        short_key = {}
        for prop in INTERESTING_PROPERTIES:
            prop_lower = prop.lower()
            for short, longname in key_list.items():
                if isinstance(longname, str) and prop_lower in longname.lower():
                    short_key[prop] = short

        cleaned_data, thermal_cams, dot_cams, missing_params = self.clean_cameras_data(short_key, data_cams)

        print(f"Skipped {thermal_cams} thermal cameras among {len(data_cams)} total cameras.")
        print(f"Skipped {dot_cams} DOT cameras among {len(data_cams)} total cameras.")
        print(f"Miss a parameter in the json to construct URL for {missing_params} cameras among {len(data_cams)} total cameras.")
        print(f"Total relevant cameras after cleaning: {len(cleaned_data)}")

        final_data = self.split_json(cleaned_data)
        print(f"Total relevant cameras for this Raspberry Pi (ID: {self.raspberry_id} / Total: {self.n_raspberry}): {len(final_data)}")
        self.total_relevant_cams = len(final_data)

        # Iterate over cameras and yield items
        for cam in final_data:
            timestamp = int(cam.get(short_key["camLastMoved"], "0"))
            cam_id = cam.get(short_key["camId"], None)
            img_name = cam.get(short_key["Screenshot"], None)
            azimuth = cam.get(short_key["Azimuth"], None)
            cam_name = cam.get(short_key["camName"], None)
            provider = cam.get(short_key["providerName"], None)

            date_path = datetime.now().strftime("%Y/%m/%d")
            img_url = f"https://img.cdn.prod.alertwest.com/data/img/{cam_id}/{date_path}/{img_name}"

            item = PyronearItem(id=cam_id, name=cam_name, azimuth=azimuth, last_moved=timestamp, image_url=img_url, provider=provider)

            yield item
