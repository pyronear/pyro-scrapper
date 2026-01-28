# PyroNear Scraper - Continuous Wildfire Detection Pipeline

A production-ready Scrapy pipeline for automated camera image scraping and wildfire detection using temporal analysis.

---

## Table of Contents

1. [Running](#running)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Architecture](#architecture)
5. [Scraping Details](#scraping-details)
6. [Inference Details](#inference-details)

---

### Running

1. **Configure your Raspberry Pi ID** in `config.py`:
   ```python
   RASPBERRY_ID = 0  # Change this to your Raspberry Pi number (0 to N_RASPBERRY-1)
   ```

2. **Start the continuous workflow**:
   ```bash
   cd ./pyro-scrapper
   python -m alertwest_scraping.continuous_workflow
   ```

That's it! The workflow automatically:
- Fetches and filters camera IDs during the day
- Scrapes images from assigned cameras
- Runs wildfire detection at night
- Cleans up images after inference

---

## Installation

First you need to git clone the repository of pyro-engine in a same folder than the repositery where alertwest_scraping is, link : https://github.com/pyronear/pyro-engine

Then in a virtual environment you will need to install the requirement of pyro-engine and install it as an executable
```bash
cd ./pyro-engine
pip install -r requirements.txt
pip install -e .
```
Then in the same virtual environment, install the requirements of alertwest_scraping 

```bash
cd ./pyro-scrapper/alertwest_scraping
pip install -r requirements.txt
```

---

## Configuration

### `config.py` - Main Configuration

This file controls the overall workflow behavior. **Modify `RASPBERRY_ID` on each Raspberry Pi device.**

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

Controls what data is fetched from the AlertWest API and where to cache it.

| Setting | Default | Description |
|---------|---------|-------------|
| `INTERESTING_PROPERTIES` | See file | Camera properties to extract (azimuth, name, location, etc.) |
| `API_URL` | AlertWest API | Endpoint for camera metadata |
| `CACHE_DIR` | `data/alertwest_cache` | Cache directory for API responses |

### `scrapy_core/settings.py` - Scrapy Settings

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

### Standard Continuous Workflow

```bash
python -m alertwest_scraping.continuous_workflow
```

The workflow cycles automatically:
- **Day**: Fetches camera IDs → Scrapes images in cycles
- **Night**: Runs wildfire detection on collected images and purges the images of the previous day

### Command-Line Options

#### Override Scrapy Settings

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
python -m alertwest_scraping.continuous_workflow --force-scrape
```

This is useful after the API changes or if you want to update the camera filter criteria.

#### Combined Example

```bash
python -m alertwest_scraping.continuous_workflow --force-scrape -s DOWNLOAD_TIMEOUT=5 -s CONCURRENT_REQUESTS=128
```

### Single Spider Runs (Advanced)

Fetch and filter all camera IDs once:
```bash
scrapy crawl spider_filtered_ids
```

Debug mode (verbose logs):
```bash
python -m alertwest_scraping.continuous_workflow -s LOG_LEVEL=DEBUG
```

---

## Architecture

### Overview

The continuous workflow orchestrates a 24-hour cycle combining camera scraping and wildfire detection.

1. **Daytime (e.g., 6 AM - 9 PM)**:
   - **Fetch Camera IDs**: Periodically retrieve and filter camera IDs from the AlertWest API based on location and other criteria.
   - **Scrape Images**: Download images from assigned cameras in a distributed manner across available Raspberry Pi devices.

2. **Nighttime (e.g., 9 PM - 6 AM)**:
   - **Wildfire Detection**: Analyze collected images for wildfire detection using the pyroengine model.
   - **Cleanup**: Remove old images.

### Components

- **Scrapy Spiders**: `alertwest_spider.py` for scraping camera metadata and images.
- **Continuous Runner**: `continuous_scraper.py` to run the spider at regular intervals.
- **Wildfire Detection**: Integrated pyroengine model inference on scraped images.
- **Logging**: Custom log formatter to reduce noise and highlight important events.

---

## Scraping Details

### Spider: `alertwest_spider.py`

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

### Items: `items.py`

`PyronearItem` fields:
- `id`: camera identifier
- `name`: camera name
- `azimuth`: camera orientation
- `last_moved`: last movement timestamp
- `image_url`: image URL to download
- `valid_url`: URL validity flag

### Pipeline: `pipelines.py`

Inherits from `scrapy.pipelines.images.ImagesPipeline` and:

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

### Error handling

A custom `LogFormatter` silences timeout noise. Counters track:
- Timeouts: images not downloaded due to deadlines
- Camera down: HTTP 4xx/5xx
- Missing URLs: incomplete JSON preventing URL construction

### Image storage structure

```
images/
└── {cam_id}/
      └── {azimuth}/
            └── {cam_id}_{scraping_timestamp}.jpg
```

### Scrapy Settings

Key Scrapy options in `settings.py`:

```python
CONCURRENT_REQUESTS = 64
CONCURRENT_ITEMS = 400
DOWNLOAD_TIMEOUT = 2
RETRY_ENABLED = False
LOG_FORMATTER = "scrapy_core.logformatter.SilentTimeoutLogFormatter"
```

## Inference Details

### Wildfire Detection with pyro-engine

The `plug_to_pyroengine.py` script enables automated wildfire detection on scraped camera images using temporal analysis.

#### How it works

1. **Temporal Filtering**: Scans the `images/` folder and identifies sequences of N consecutive images (default: 6) where timestamps are separated by at most a specified gap (default: 120 seconds).

2. **Detection**: Each valid sequence is processed folder-by-folder through pyroengine's wildfire detection model.

3. **Output**: Folders containing sequences with detected wildfires are copied to an `annotations/` directory for further review.

#### Usage

First, ensure you're in an environment with pyroengine installed:

```bash
conda activate pyronear
python plug_to_pyroengine.py --n 6 --max-gap 90 --conf-thresh 0.15
```

#### Options

- `--images-dir`: Root images directory (defaults to `images/` next to the script)
- `--n`: Required number of consecutive images in a sequence (default: 6)
- `--max-gap`: Maximum allowed gap in seconds between consecutive images (default: 60)
- `--conf-thresh`: Confidence threshold for wildfire detection (default: 0.15)
- `--output-dir`: Output directory for detected sequences (default: `annotations/` next to images)

#### Example

```bash
# Analyze sequences of 8 images with 30-second max gap and 0.20 confidence threshold
python plug_to_pyroengine.py --n 8 --max-gap 30 --conf-thresh 0.20 --output-dir ./detections
```

#### Prerequisites for Detection

Before running wildfire detection, install pyroengine and its dependencies:

```bash
cd ../../pyro-engine
pip install -r requirements.txt
pip install -e .
```

---


## Mécanisme de scraping (détail technique)

1. Le spider `scrapy_core/spiders/alertwest_spider.py` :
     - Envoie une requête HTTP GET vers `API_URL = "https://api.cdn.prod.alertwest.com/api/getCameraDataByLoc"`.
     - Parse le corps JSON de la réponse et récupère deux objets principaux :
         - `key_list` : mapping des clés courtes vers les noms de propriétés (utilisé pour retrouver les champs dynamiques renvoyés par l'API).
         - `data_cams` : liste des objets caméra.
     - Construit `short_key` en comparant les noms de propriétés intéressantes (ex : `Azimuth`, `camLastMoved`, `camId`, `Screenshot`, `camName`) avec `key_list` pour déterminer quelle clé courte correspond à chaque propriété.
     - Pour chaque caméra dans `data_cams` :
         - Lit les valeurs (id, nom, azimut, timestamp, nom d'image).
         - Si `cam_id` et `img_name` sont présents, construit l'URL d'image :
             `https://img.cdn.prod.alertwest.com/data/img/{cam_id}/{YYYY/MM/DD}/{img_name}` (la date utilisée est la date courante).
         - Crée un `PyronearItem` avec les champs remplis et le `image_url` construit, puis `yield item`.

2. Items (`scrapy_core/items.py`) :
     - `PyronearItem` est un conteneur Scrapy standard définissant les champs attendus. Le pipeline et le spider s'appuient dessus pour transporter métadonnées + URL.

3. Pipeline `AlertwestImagePipeline` (`scrapy_core/pipelines.py`) :
     - Hérite de `scrapy.pipelines.images.ImagesPipeline`.
     - Méthodes principales :
         - `open_spider(self, spider)` : initialise timers, compteurs et la barre de progression `tqdm`. Récupère `spider.total_cams` pour fixer la taille de la barre.
         - `get_media_requests(self, item, info)` :
             - Appelée pour chaque `item`. Si `item['image_url']` existe, elle met à jour la barre de progression puis retourne une `scrapy.Request` pointant vers l'URL d'image en transférant les métadonnées utiles via `meta` (ex : `id`, `azimuth`, `last_moved`).
             - Si l'URL est absente, incrémente un compteur `no_url`.
         - `media_failed(self, failure, request, info)` : intercepte les erreurs réseau/timout et incrémente des compteurs (`timeout_cam`, `failed_cam`) selon la nature de l'erreur.
         - `file_path(self, request, response=None, info=None, item=None)` : construit le chemin local de sauvegarde pour chaque image. Format : ``{cam_id}/{azimuth}/{cam_id}_{scraping_timestamp}.jpg`` (azimuth vaut `unknown` si absent).
         - `close_spider(self, spider)` : affiche un résumé (nombre d'échecs, d'URLs manquantes, temps écoulé) et ferme la barre de progression.

4. Réglages clés (`scrapy_core/settings.py`) :
     - `FEEDS` : configuration pour exporter les métadonnées en JSON (`alertwest.json`).
     - Concurrence élevée pour maximiser le throughput : `CONCURRENT_REQUESTS = 64`, `CONCURRENT_REQUESTS_PER_DOMAIN = 32`, `CONCURRENT_ITEMS = 400`.
     - Timeout réduit pour favoriser la vitesse : `DOWNLOAD_TIMEOUT = 2` (modifiable via la ligne de commande `-s DOWNLOAD_TIMEOUT=3`).
     - `LOG_FORMATTER` personnalisé pour cacher les logs de timeout.
     - `RETRY_ENABLED = False` pour ne pas retenter les requêtes longues.