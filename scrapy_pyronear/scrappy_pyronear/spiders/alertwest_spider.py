"""AlertWest spider for scraping camera images."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import scrapy
from astral import LocationInfo
from astral.sun import sun
from scrappy_pyronear.items import PyronearItem
from timezonefinder import TimezoneFinder

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

        self.thermal_cams_ = 0
        self.dot_cams_ = 0
        self.missing_params_ = 0
        self.offline_cams_ = 0
        self.night_cams_ = 0

    def is_daytime_by_coords(self, latitude, longitude):
        """Check if it's currently daytime at given coordinates.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            bool: True if daytime, False if nighttime
                  Returns False if unable to calculate (edge cases, polar regions, etc.)

        """
        try:
            # Get or initialize timezone resolver
            if not hasattr(self, "_tz_finder"):
                self._tz_finder = TimezoneFinder()

            lat = float(latitude)
            lon = float(longitude)

            # Find local timezone from position
            tz_name = self._tz_finder.timezone_at(lat=lat, lng=lon)
            local_tz = ZoneInfo(tz_name)

            location = LocationInfo(
                latitude=lat,
                longitude=lon,
                timezone=tz_name,
            )

            now_local = datetime.now(local_tz)

            s = sun(location.observer, date=now_local.date(), tzinfo=local_tz)
            sunrise = s["sunrise"]
            sunset = s["sunset"]

            return sunrise <= now_local <= sunset  # Consider tightening window to avoid any night images

        except Exception:
            # If calculation impossible (extreme coords, missing tz), consider it night
            return False

    def clean_cameras_data(self, short_key_cams, short_key_locs, data_cams, data_locs):
        """Clean the JSON data by keeping only relevant items."""
        cleaned_file_json = CACHE_DIR / "alertwest_cleaned_json.json"
        cleaned_json = []

        # Create location mapping by ID for fast access
        locs_by_id = {}
        for loc in data_locs:
            loc_id = loc.get("id")
            if loc_id:
                locs_by_id[loc_id] = loc

        for cam in data_cams:
            cam_id_cams = cam.get(short_key_cams.get("camId"))
            img_name = cam.get(short_key_cams.get("Screenshot"))
            cam_name = (cam.get(short_key_cams.get("camName")) or "").lower()
            provider = (cam.get(short_key_cams.get("providerName")) or "").lower()
            cam_offline = cam.get(short_key_cams.get("camOffline"))

            # Find corresponding location via 'lid' (location ID)
            cam_loc = None
            cam_location_id = cam.get("lid")  # This is the key to find the location
            if cam_location_id and cam_location_id in locs_by_id:
                loc = locs_by_id[cam_location_id]
                cam_loc = [loc.get(short_key_locs.get("locLat")), loc.get(short_key_locs.get("locLon"))]

            if "thermal" in cam_name:
                self.thermal_cams_ += 1
                continue
            if "dot" in provider:
                self.dot_cams_ += 1
                continue
            if cam_offline == 1:
                self.offline_cams_ += 1
                continue
            if not cam_id_cams or not img_name:
                self.missing_params_ += 1
                continue
            if not cam_loc or cam_loc == [None, None]:
                continue
            if not self.is_daytime_by_coords(cam_loc[0], cam_loc[1]):
                self.night_cams_ += 1
                continue

            cleaned_json.append(cam)

        print(
            f"\nSkipped {self.thermal_cams_} thermal cameras, {self.dot_cams_} DOT cameras, {self.offline_cams_} offline cameras among {len(data_cams)} total cameras."
        )
        print(
            f"Miss a parameter in the json to construct URL for {self.missing_params_} cameras among {len(data_cams)} total cameras."
        )
        print(f"Skipped {self.night_cams_} nighttime cameras among {len(data_cams)} total cameras.")

        print(f"Total relevant cameras after cleaning: {len(cleaned_json)}")

        # Store cleaned JSON
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
                # location_id =cam.get("lid"),
                # latitude=cam.get(short_key["locLat"]),
                # longitude=cam.get(short_key["locLon"]),
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
            # Load cache directly without overwriting
            with open(cache_file, "r") as f:
                payload = json.load(f)
            final_data = payload["cams"]
            short_key_cams = payload.get("short_key_cams", payload.get("short_key"))  # Backward compatibility
            yield from self.items_from_data(final_data, short_key_cams)

    def parse(self, response):
        """Parse the API response, clean & split data, cache it, and yield items."""
        data = json.loads(response.text)

        cams_keys = data.get("data", {}).get("cams", {}).get("key", {})
        locs_keys = data.get("data", {}).get("locs", {}).get("key", {})

        data_cams = data.get("data", {}).get("cams", {}).get("data", [])
        data_locs = data.get("data", {}).get("locs", {}).get("data", [])

        # Map properties to short keys for cams ONLY
        short_key_cams = {
            prop: short
            for prop in INTERESTING_PROPERTIES
            for short, longname in cams_keys.items()
            if isinstance(longname, str) and prop.lower() in longname.lower()
        }

        # Map properties to short keys for locs ONLY
        short_key_locs = {
            prop: short
            for prop in INTERESTING_PROPERTIES
            for short, longname in locs_keys.items()
            if isinstance(longname, str) and prop.lower() in longname.lower()
        }

        # Clean and split data
        cleaned_data = self.clean_cameras_data(short_key_cams, short_key_locs, data_cams, data_locs)
        final_data = self.split_json(cleaned_data)

        # Cache for this raspberry
        cache_file = CACHE_DIR / f"alertwest_cache_raspberry_{self.raspberry_id}.json"
        with open(cache_file, "w") as f:
            json.dump({"short_key_cams": short_key_cams, "short_key_locs": short_key_locs, "cams": final_data}, f)

        yield from self.items_from_data(final_data, short_key_cams)
