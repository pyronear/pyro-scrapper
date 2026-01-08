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

    def extract_keys(self, data):
        """Extract short keys for cameras and locations from the API response."""
        cams_keys = data.get("data", {}).get("cams", {}).get("key", {})
        locs_keys = data.get("data", {}).get("locs", {}).get("key", {})

        # Map properties to short keys for cams
        short_key_cams = {
            prop: short
            for prop in INTERESTING_PROPERTIES
            for short, longname in cams_keys.items()
            if isinstance(longname, str) and prop.lower() in longname.lower()
        }

        # Map properties to short keys for locs
        short_key_locs = {
            prop: short
            for prop in INTERESTING_PROPERTIES
            for short, longname in locs_keys.items()
            if isinstance(longname, str) and prop.lower() in longname.lower()
        }

        return short_key_cams, short_key_locs

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

    def clean_cameras_data(self, short_key_cams, data_cams):
        """Clean the JSON data by keeping only relevant items."""
        cleaned_file_json = CACHE_DIR / "alertwest_cleaned_json.json"
        cleaned_json = []

        for cam in data_cams:
            cam_id_cams = cam.get(short_key_cams.get("camId"))
            img_name = cam.get(short_key_cams.get("Screenshot"))
            cam_name = (cam.get(short_key_cams.get("camName")) or "").lower()
            provider = (cam.get(short_key_cams.get("providerName")) or "").lower()
            cam_offline = cam.get(short_key_cams.get("camOffline"))

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

            cleaned_json.append(cam)

        print(
            f"\nSkipped {self.thermal_cams_} thermal cameras, {self.dot_cams_} DOT cameras, {self.offline_cams_} offline cameras among {len(data_cams)} total cameras."
        )
        print(
            f"Miss a parameter in the json to construct URL for {self.missing_params_} cameras among {len(data_cams)} total cameras."
        )

        # Store cleaned JSON
        with open(cleaned_file_json, "w") as f:
            json.dump(cleaned_json, f)

        return cleaned_json
    
    def filter_night_cameras(self, cleaned_json, data_locs, short_key_locs):
        """Filter out cameras that are currently in nighttime."""
        filtered_cams = []
        self.night_cams_ = 0

        locs_by_id = {loc.get("id"): loc for loc in data_locs if loc.get("id")}

        for cam in cleaned_json:
            loc_id = cam.get("lid")
            loc = locs_by_id.get(loc_id)

            if not loc:
                continue

            lat = loc.get(short_key_locs.get("locLat"))
            lon = loc.get(short_key_locs.get("locLon"))

            if lat is None or lon is None:
                continue

            if not self.is_daytime_by_coords(lat, lon):
                self.night_cams_ += 1
                continue

            filtered_cams.append(cam)

        print(
            f"Skipped {self.night_cams_} nighttime cameras "
            f"out of {len(cleaned_json)} cleaned cameras."
        )

        with open(CACHE_DIR / "alertwest_daytime_filtered_json.json", "w") as f:
            json.dump(filtered_cams, f)

        return filtered_cams

    def split_json(self, data):
        """Split cameras across Raspberry Pi instances."""
        splitted_for_me = []

        for rid in range(self.n_raspberry):
            subset = [cam for idx, cam in enumerate(data) if idx % self.n_raspberry == rid]

            with open(CACHE_DIR / f"alertwest_split_raspberry_{rid}.json", "w") as f:
                json.dump(subset, f)

            if rid == self.raspberry_id:
                splitted_for_me = subset

        return splitted_for_me

    def save_cache(self, short_key_cams, short_key_locs, locs):
        """Save keys and locations required for refresh cycles."""
        with open(CACHE_DIR / "alertwest_keys.json", "w") as f:
            json.dump(
                {
                    "short_key_cams": short_key_cams,
                    "short_key_locs": short_key_locs,
                    "locs": locs,
                },
                f,
            )

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
        short_key_cams, short_key_locs = self.extract_keys(data)

        data_cams = data["data"]["cams"]["data"]
        data_locs = data["data"]["locs"]["data"]

        cleaned = self.clean_cameras_data(short_key_cams, data_cams)
        filtered = self.filter_night_cameras(cleaned, data_locs, short_key_locs)
        final = self.split_json(filtered)

        self.save_cache(short_key_cams, short_key_locs, data_locs)

        return final, short_key_cams
    
    def process_from_clean_cache(self):
        with open(CACHE_DIR / "alertwest_cleaned_json.json") as f:
            cleaned = json.load(f)

        with open(CACHE_DIR / "alertwest_keys.json") as f:
            keys = json.load(f)

        filtered = self.filter_night_cameras(
            cleaned,
            keys["locs"],
            keys["short_key_locs"],
        )

        final = self.split_json(filtered)

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
