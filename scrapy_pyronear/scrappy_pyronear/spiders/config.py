from pathlib import Path

# List of interesting properties to extract from the AlertWest API response
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

# AlertWest API URL to fetch camera data
API_URL = "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc"

# Cache directory to store cleaned and split JSON files
CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)