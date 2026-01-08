# AlertWest Image Scraping Pipeline

This repository provides a high‑throughput Scrapy pipeline to download camera images from AlertWest, plus a continuous runner to execute the spider at a fixed interval.

# ===== STARTER INFO =====
## Prerequisites

- Python 3.12.0
- Conda or pip for dependency management

## Installation

```bash
conda create --name pyronear python=3.12
conda activate pyronear
pip install -r requirements.txt
```

# ===== RUNNING INFO =====
## Continuous Scraping (recommended entrypoint)

The continuous runner is the easiest way to keep images up‑to‑date.

- What it does: repeatedly launches the Scrapy spider at a fixed interval (no overlap). It logs each cycle, handles Ctrl+C gracefully, and reuses your Scrapy project settings, spider, and pipelines.
- How it works with Scrapy: it shells out `scrapy crawl alertwest` inside this project, so the spider, pipelines, and `settings.py` remain the single source of truth. The runner only schedules runs; it doesn’t change scraping logic.
- The API call to fetch the JSON containing all the cameras metadata is only called every few cycles. The number of cycles without fetching the JSON is customizable.

### Quick start

To customize the scrapping to your own needs, please modify `config.py` and `scrappy_pyronear/spiders/config.py` as specified in the next section.

```bash
# Launch continuous scrapper
python -m scrapy_pyronear.continuous_scraper 

# Combined: Continuous scrapper + Scrapy settings
python -m scrapy_pyronear.continuous_scraper -s DOWNLOAD_TIMEOUT=3 -s CONCURRENT_ITEMS=100
```

Notes
- Graceful stop: press Ctrl+C; the current cycle finishes, then the runner exits.
- If a cycle takes longer than the interval, the next cycle starts immediately after.
- Outputs: `alertwest.json` is overwritten each cycle (per `settings.py`), and images are saved under `images/`.

### Configuration 

Parameters in `config.py`
| Setting | Default | Description |
|--------|---------|-------------|
| `INTERVAL` | 60s | Duration between each scrapping cycle |
| `N_RASPBERRY` | 2 | Total number of Raspberry Pi devices |
| `RASPBERRY_ID` | 0 | ID of the current Raspberry Pi |
| `CYCLE_REFRESH_JSON` | 100 | Number of cycles without refreshing the JSON to download the images |
| `LAUNCH_WITH_CLEANING` | True | Indicates if the fetching and cleaning of the JSON from `alertwest` is needed or if it is already downloaded in `data/alertwest_cache` |

Parameters in `scrappy_pyronear/spiders/config.py` :
| Setting | Default | Description |
|--------|---------|-------------|
| `INTERESTING_PROPERTIES` | Defined in the file | Properties fetched from the API call |
| `API_URL` | "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc" | URL to use fir the API call to fetch the metadata of the cameras |
| `CACHE_DIR` | "data/alertwest_cache" | Folder where the cleaned jsons are saved to avoid unnecessary API calls |

## One‑off crawl (single run)

```bash
scrapy crawl alertwest
```

### Common settings (see `settings.py`)

Examples:

| Setting | Default | Description |
|--------|---------|-------------|
| `DOWNLOAD_TIMEOUT` | 2s | Max time to download an image |
| `CONCURRENT_ITEMS` | 400 | Parallel items processed in the pipeline |
| `CONCURRENT_REQUESTS` | 64 | Max concurrent HTTP requests |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | 32 | Concurrent requests per domain |

### Export metadata to JSON

```bash
scrapy crawl alertwest -o alertwest.json
```

### Debug mode

```bash
scrapy crawl alertwest -s LOG_LEVEL=DEBUG
```

## Tests

```bash
# Bash / Linux / macOS
pytest -v tests/

# Windows PowerShell
pytest -v .\tests\
```

# Project structure

```
scrappy_pyronear/
├── spiders/
│   └── alertwest_spider.py      # Main spider
├── items.py                     # Item definitions
├── pipelines.py                 # Image download pipeline
├── settings.py                  # Scrapy configuration
└── logformatter.py              # Custom log formatter
images/                          # Output directory (generated)
tests/                           # Unit tests
alertwest.json                   # Optional JSON export of metadata
```

# How it works

## 1) Spider (`alertwest_spider.py`)

- Sends a GET request to the AlertWest API.
- Parses the JSON response to extract:
  - `key_list`: mapping from short keys to property names.
  - `data_cams`: the list of cameras.
- Maps interesting properties (Azimuth, camId, Screenshot, camLastMoved, camName, etc.) to their short keys.
- For each camera, builds the image URL:

```
https://img.cdn.prod.alertwest.com/data/img/{cam_id}/{YYYY/MM/DD}/{img_name}
```

- Yields `PyronearItem` objects with metadata and `image_url`.

## 2) Items (`items.py`)

`PyronearItem` fields:
- `id`: camera identifier
- `name`: camera name
- `azimuth`: camera orientation
- `last_moved`: last movement timestamp
- `image_url`: image URL to download
- `valid_url`: URL validity flag

## 3) Pipeline (`pipelines.py`)

Inherits from `scrapy.pipelines.images.ImagesPipeline` and:

| Method | Purpose |
|--------|---------|
| `open_spider()` | Initializes counters, timers, and a progress bar |
| `get_media_requests()` | Generates parallel image download requests |
| `media_failed()` | Captures errors (timeouts, connection issues) and updates counters |
| `file_path()` | Storage structure: `{cam_id}/{azimuth}/{cam_id}_{scraping_timestamp}.jpg` |
| `close_spider()` | Prints a summary (failures, missing URLs, elapsed time) |

## 4) Concurrency tuning

- `CONCURRENT_REQUESTS = 64`: avoid overwhelming the network
- `CONCURRENT_REQUESTS_PER_DOMAIN = 32`: be polite to the remote host
- `CONCURRENT_ITEMS = 400`: speed up pipeline processing
- `RETRY_ENABLED = False`: skip retries for faster throughput
- `DOWNLOAD_TIMEOUT = 2s`: aggressive timeout for speed (tune as needed)

## 5) Error handling

A custom `LogFormatter` silences timeout noise. Counters track:
- Timeouts: images not downloaded due to deadlines
- Camera down: HTTP 4xx/5xx
- Missing URLs: incomplete JSON preventing URL construction

## 6) Image storage structure

```
images/
└── {cam_id}/
      └── {azimuth}/
            └── {cam_id}_{scraping_timestamp}.jpg
```

## Scrapy Settings

Key Scrapy options in `settings.py`:

```python
CONCURRENT_REQUESTS = 64
CONCURRENT_ITEMS = 400
DOWNLOAD_TIMEOUT = 2
RETRY_ENABLED = False
LOG_FORMATTER = "scrappy_pyronear.logformatter.SilentTimeoutLogFormatter"
```

## Output example

```
Downloading images 🚀 : 100%|█████████████████████████████| 11702/11702 images

URL retrieved but camera is down for 1524 cameras among 11702 total cameras.
Miss a parameter in the json to construct URL for 999 cameras among 11702 total cameras.
Timed out for 45 cameras among 11702 total cameras.
Time taken: 2.53 minutes
```

## Helpers for troubleshooting

### Slow scraping

Increase concurrency:
```bash
scrapy crawl alertwest -s CONCURRENT_REQUESTS=128 CONCURRENT_ITEMS=500
```

### Too many timeouts

Increase the timeout:
```bash
scrapy crawl alertwest -s DOWNLOAD_TIMEOUT=10
```