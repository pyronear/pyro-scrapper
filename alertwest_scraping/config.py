"""Configuration parameters for the continuous scraper."""

from pathlib import Path

# Duration (in seconds) between each scraping cycle
INTERVAL = 600

# Number of raspberry pi devices
N_RASPBERRY = 2

# ID of this raspberry pi device (must be between 0 and N_RASPBERRY - 1)
RASPBERRY_ID = 0

# Cache directory to store cleaned and split JSON files
CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Number of consecutive images to consider as a sequence for inference
N_CONSECUTIVE = 6

# Number of seconds allowed between images in a sequence (should be >= INTERVAL to find valid sequences)
MAX_GAP_SECONDS = INTERVAL * 1.5

# Minimum number of images in a sequence that must have fire detections to be sent to the API
MIN_DETECTIONS = N_CONSECUTIVE / 2

# Confidence threshold for fire detection lower than the default value because filter on the number of detections in the sequence
CONF_THRESH = 0.1