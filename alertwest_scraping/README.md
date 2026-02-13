# PyroNear Scraper - Continuous Wildfire Detection Pipeline

A production-ready Scrapy pipeline for automated camera image scraping and wildfire detection using temporal analysis.

---

## Table of Contents

0. [Installation](#installation)
1. [Running](#running)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Architecture](#architecture)
5. [Scraping Details](#scraping-details)
6. [Inference Details](#inference-details)

--- 

### Installation

First you need to git clone the repositories of pyro-engine and pyro-annotator in the same parent folder as pyro-scrapper:

```bash
git clone https://github.com/pyronear/pyro-engine.git
git clone https://github.com/pyronear/pyro-annotator.git
```

Then in a virtual environment you will need to install the requirements of pyro-engine and install it as an editable package:
```bash
cd ./pyro-engine
pip install -r requirements.txt
pip install -e .
```

Install pyro-annotator (needed for annotation API client code used by the pipeline):

```bash
cd ./pyro-annotator/annotation_api
pip install -e .
```

Then in the same virtual environment, install the requirements of alertwest_scraping.

```bash
cd ./pyro-scrapper/alertwest_scraping
pip install -r requirements.txt
```

**Annotation API Credentials**

Create a `.env` file in the pyro-scrapper root with your pyronear annotation API credentials (otherwise all detected wildfire sequences will fail to be sent to the API):

```
MAIN_ANNOTATION_LOGIN=your_username
MAIN_ANNOTATION_PASSWORD=your_password
```

These credentials are used by `import_yolo_sequence.py` to authenticate with `https://annotationapi.pyronear.org/`.

---

### Running

1. **Configure the number of Raspberry working in parallel and your Raspberry Pi ID** in `.\pyro-scrapper\alertwest_scraping\config.py`:
   ```python
    N_RASPBERRY = 2  # Total number of Raspberry Pi devices in your network
    RASPBERRY_ID = 0  # Change this to your Raspberry Pi number (0 to N_RASPBERRY-1)
   ```
   **Modify `RASPBERRY_ID` on each Raspberry Pi device.**

2. **Start the continuous workflow**:
   ```bash
   cd ./pyro-scrapper
   python -m alertwest_scraping.continuous_workflow
   ```

That's it! The workflow automatically:
- Fetches and filters camera IDs during the day
- Scrapes images from assigned cameras
- Runs wildfire detection at night and send them to the annotation API
- Cleans up images after inference
- ... repeating until a manual stop.

---

### Tests

Run the full test suite from the repository root:

```bash
pytest ./alertwest_scraping/tests
```

---

## Configuration
One should prioritize tuning the parameters in the `config.py` and 'settings.py` files once the best parameters are found for normal operation. 

### `.\pyro-scrapper\alertwest_scraping\config.py` - Main Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `INTERVAL` | 60s | Wait time between scraping cycles during the day |
| `N_RASPBERRY` | 2 | Total number of Raspberry Pi devices in your network |
| `RASPBERRY_ID` | 0 | **ID of this Raspberry Pi (0 to N_RASPBERRY-1)** - Change per device |
| `CACHE_DIR` | `data/alertwest_cache` | Directory for cached JSON files of IDs for each Raspberry Pi |

**⚠️ Important**: On each Raspberry Pi, update `RASPBERRY_ID`:
- Raspberry Pi 1: `RASPBERRY_ID = 0`
- Raspberry Pi 2: `RASPBERRY_ID = 1`
- etc.

### `scrapy_core/spiders/config.py` - Spider Configuration

Controls some important features of the pipeline at different scale and stape (fetching, inference/Annotation_API). One should try to tune these parameters to find the best trade-off between speed and reliability. They can be overridden via CLI when running the workflow (see [Usage](#usage) section).

### `.\pyro-scrapper\alertwest_scraping\scrapy_core\settings.py` - Scrapy Settings

Fine-tune performance during scraping. Can be overridden via CLI with `-s`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CONCURRENT_REQUESTS` | 64 | Max parallel HTTP requests |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | 32 | Requests per domain (be polite) |
| `CONCURRENT_ITEMS` | 400 | Parallel items in pipeline |
| `DOWNLOAD_TIMEOUT` | 2s | Max wait for image download |
| `RETRY_ENABLED` | False | Disable retries for speed |
| ...

---

## Usage
One can use the CLI options to override Scrapy settings for exploring new behaviors with new parameters or to force re-fetching of camera IDs.

### Standard Continuous Workflow

```bash
python -m alertwest_scraping.continuous_workflow
```

### Command-Line Options

#### Override Scrapy Settings
Examples: 

Increase timeout for slow networks:
```bash
python -m alertwest_scraping.continuous_workflow -s DOWNLOAD_TIMEOUT=5
```

Increase concurrency for faster scraping:
```bash
python -m alertwest_scraping.continuous_workflow -s CONCURRENT_REQUESTS=128 -s CONCURRENT_ITEMS=500
```

#### Force Re-filtering Camera IDs

Normally, `good_ids.json` once fetched for the first time is cached. Force a refresh:
```bash
python -m alertwest_scraping.continuous_workflow --force-get-ids
```

This is useful after the API changes or if you want to update the camera filter criteria.
---

## Architecture

### Overview

The continuous workflow orchestrates a 24-hour cycle combining camera scraping and wildfire detection.

1. **Daytime in US (using a fix location)**:
    - **Scrape Images**: Each devices download and store images from assigned cameras in a distributed manner across available Raspberry Pi devices.

2. **Nighttime in US (using a fix location)**:
   - **Wildfire Detection**: Analyze collected images for wildfire detection using the pyroengine model.
   - **API Submission**: Automatically submit detected wildfire sequences to the pyro-annotator API for annotation and further processing.
   - **Cleanup**: Remove old images.

### Components

- **Continuous Runner**: `continuous_workflow.py` continuous loop script managing the day/night cycle and orchestrating the scraping and inference processes.
- **Scrapy Spiders and their associated pipelines**: `scrapy_core/...` for scraping camera metadata and images.
- **Orchestration Inference / Annotation API**: `orchestration_inference_send_annotation_api.py` pipeline managing wildfire detection and API submission.
- **Inference**: `inference.py` Use of the pyroengine model inference on scraped images sequences.
- **API Submission**: `send_annotation_api.py` Automated submission of detected wildfire sequences to the pyro-annotator API.

---

## Scraping Details

### 2 Spiders: 

First spider (`spider_filtered_ids.py`) fetches camera metadata and filters camera IDs based on criteria (e.g., location). The second spider (`spider_get_images.py`) uses the filtered IDs to scrape images.

Both doing approximetly the same things but not on the same cameras : 
- Sends a GET request to the AlertWest API.
- Parses the JSON response to extract interesting properties.
- Maps interesting properties (Azimuth, camId, Screenshot, camName, etc.) to their short keys.
- For each camera, builds the image URL:

```
https://img.cdn.prod.alertwest.com/data/img/{cam_id}/{YYYY/MM/DD}/{img_name}
```

- Yields `PyronearItem` objects with metadata.

### Items: `items.py`

Give the metadata needed for an item to have.

### 2 Pipeline: `pipelines.py`

2 pipelines associated each with their respective spider. They are acting on the items yielded by the spiders. 

The `AlertwestImagePipeline` inherits from `scrapy.pipelines.images.ImagesPipeline` and is responsible for downloading images and saving them with a specific structure.
| Method | Purpose |
|--------|---------|
| `open_spider()` | Initializes counters, timers, and a progress bar |
| `get_media_requests()` | Generates parallel image download requests |
| `media_failed()` | Captures errors (timeouts, connection issues) and updates counters |
| `file_path()` | Storage structure: `{cam_id}/{azimuth}/{cam_id}_{scraping_timestamp}.jpg` |
| `close_spider()` | Prints a summary (failures, missing URLs, elapsed time) |

### Concurrency tuning

- `CONCURRENT_REQUESTS = 64`: avoid overwhelming the network
- `CONCURRENT_REQUESTS_PER_DOMAIN = 32`: be polite to the remote host
- `CONCURRENT_ITEMS = 400`: speed up pipeline processing
- `RETRY_ENABLED = False`: skip retries for faster throughput
- `DOWNLOAD_TIMEOUT = 2s`: aggressive timeout for speed (tune as needed)

### Image storage structure

```
images/
└── {cam_name}/
      └── {azimuth}/
            └── {cam_id}_{scraping_timestamp}_{lat}_{lon}_{cam_name}.jpg
```

## Inference Details

### Wildfire Detection with pyro-engine

The `orchestration_inference_send_annotation_api.py` pipeline enables automated wildfire detection on scraped camera images using temporal analysis and API submission.

#### How it works

1. **Temporal Filtering**: Scans the `images/` folder and identifies sequences of N consecutive images where timestamps are separated by at most a specified gap.

2. **Detection**: Each valid sequence is processed through the inference module (`inference.py`) which runs pyroengine's fire detection model on each image in the sequence.

3. **API Submission**: Sequences with detected wildfires (enough detections) are formatted as YOLO datasets and submitted to the pyro-annotator API via the annotation API integration module (`send_annotation_api.py`).


#### API Integration Details

When a fire sequence is detected:

1. **Unique ID Generation**: Each sequence receives a stable, collision-free ID via CRC32 hash of `{cam_id}:{azimuth}:{timestamp}`. This allows safe re-ingestion without API conflicts.

2. **API Submission**: Images and normalized boxes are sent directly to the annotation API without creating local copies.

3. **Credentials**: API authentication uses environment variables from `.env` file (see **Installation** section).
---

## Next steps / TO DO

- ✅ **API Integration** - Annotation API now integrated via `send_annotation_api.py` with automatic YOLO format conversion and submission (completed)
- 🔄 **Doing robust test detection with Real Fire Images** - Validate detection accuracy with actual wildfire imagery
- Integrate the pyro-engine and pyro-annotator dependencies directly into the pyro-scrapper requirements.txt to allow setup via a single `pip install -r requirements.txt` command
- Verify scraping frequency to ensure all images captured during the day can be processed during the night
- Integrate CodeCarbon library to quantify environmental impact of the code