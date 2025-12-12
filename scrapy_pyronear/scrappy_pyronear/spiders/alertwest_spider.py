import scrapy
import json
from datetime import datetime
from scrappy_pyronear.items import PyronearItem   # <<< import item propre

# Execute the code 
# NORMAL : scrapy crawl alertwest
# WITH DEBUG : scrapy crawl alertwest -s LOG_LEVEL=DEBUG

# INDIVIDUAL PROPERTIES TO EXTRACT FROM THE API RESPONSE
INTERESTING_PROPERTIES = ["Azimuth", "camLastMoved", "camId", "Screenshot", "camOffline","camName"]
API_URL = "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc"

class AlertwestSpider(scrapy.Spider):
    name = "alertwest"
    start_urls = [API_URL]

    # automatically called when the spider is opened
    def parse(self, response):
        # Fetch the JSON data
        data = json.loads(response.text)

        key_list = data.get("data", {}).get("cams", {}).get("key", {})
        data_cams = data.get("data", {}).get("cams", {}).get("data", [])

        self.total_cams = len(data_cams)

        # Construct a mapping from property to short key ( ex: "Azimuth" -> "p" )
        short_key = {}
        for prop in INTERESTING_PROPERTIES:
            prop_lower = prop.lower()
            for short, longname in key_list.items():
                if isinstance(longname, str) and prop_lower in longname.lower():
                    short_key[prop] = short

        # Iterate over cameras and yield items
        for cam in data_cams:
            timestamp = int(cam.get(short_key["camLastMoved"], '0'))
            cam_id = cam.get(short_key["camId"], None)
            img_name = cam.get(short_key["Screenshot"], None)
            azimuth = cam.get(short_key["Azimuth"], None)
            cam_name = cam.get(short_key["camName"], None)

            # Construct image URL
            if cam_id and img_name :
                date_path = datetime.now().strftime("%Y/%m/%d")
                img_url = f"https://img.cdn.prod.alertwest.com/data/thumb/{cam_id}/{date_path}/{img_name}"

            else :
                img_url = None

            # Create and yield the item
            item = PyronearItem(
                id=cam_id,
                name=cam_name,
                azimuth=azimuth,
                last_moved=timestamp,
                image_url=img_url
            )

            yield item