"""Configuration parameters for the continuous scraper."""

from pathlib import Path

# Duration (in seconds) between each scraping cycle
INTERVAL = 60

# Number of raspberry pi devices
N_RASPBERRY = 8

# ID of this raspberry pi device (must be between 0 and N_RASPBERRY - 1)
RASPBERRY_ID = 0

# Cache directory to store cleaned and split JSON files
CACHE_DIR = Path("data/alertwest_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Number of consecutive images to consider as a sequence for inference, set as same as the default in Predictor (can be tuned based on validation results)
N_CONSECUTIVE = 8

# Frame size for resizing images before inference
FRAME_SIZE = (1280, 720)

# Number of seconds allowed between images in a sequence (should be >= INTERVAL to find valid sequences)
MAX_GAP_SECONDS = INTERVAL * 3

# # Minimum number of images in a sequence that must have fire detections to be sent to the API
# MIN_DETECTIONS = N_CONSECUTIVE / 2

# Confidence threshold set same as the default in Predictor (can be tuned based on validation results)
CONF_THRESH = 0.15  # confidence threshold above which an alert is considered active
MODEL_CONF_THRESH = 0.05  # per-frame confidence threshold passed to the YOLO model
