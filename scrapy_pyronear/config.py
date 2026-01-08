"""
Configuration parameters for the continuous scraper.
"""

# Duration (in seconds) between each scraping cycle
INTERVAL = 60 

# Number of raspberry pi devices
N_RASPBERRY = 2

# ID of this raspberry pi device (should be between 0 and N_RASPBERRY - 1)
RASPBERRY_ID = 0

# Number of cycle without refreshing the JSON data
CYCLE_REFRESH_JSON = 100

# Launch with cleaning of the JSON data (takes time to ensure to keep only high-quality cameras)
LAUNCH_WITH_CLEANING = True