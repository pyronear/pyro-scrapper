"""
Configuration parameters for the continuous scraper.
"""
from pathlib import Path

# Duration (in seconds) between each scraping cycle
INTERVAL = 60 

# Number of raspberry pi devices
N_RASPBERRY = 2

# ID of this raspberry pi device (should be between 0 and N_RASPBERRY - 1)
RASPBERRY_ID = 0

# Launch with cleaning of the JSON data (takes time to ensure to keep only high-quality cameras)
LAUNCH_WITH_CLEANING = True

# Cache directory to store cleaned and split JSON files
CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)