"""Configuration for the AlertWest spiders."""

from pathlib import Path

# List of interesting properties to extract from the AlertWest API response
INTERESTING_PROPERTIES = [
    "camAzimuth",
    "camLastMoved",
    "camId",
    "camScreenshot",
    "camOffline",
    "camName",
    "providerName",
    "locId",
    "locLat",
    "locLon",
    "camLocation",
]

# AlertWest API URL to fetch camera data
API_URL = "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc"

# Cache directory to store cleaned and split JSON files
CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
