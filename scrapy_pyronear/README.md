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
# At the root of the project
pip install -e .

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

---

# Wildfire Detection with pyro-engine

The `plug_to_pyroengine.py` script enables automated wildfire detection on scraped camera images using temporal analysis.

## How it works

1. **Temporal Filtering**: Scans the `images/` folder and identifies sequences of N consecutive images (default: 6) where timestamps are separated by at most a specified gap (default: 60 seconds).

2. **Detection**: Each valid sequence is processed folder-by-folder through pyroengine's wildfire detection model.

3. **Output**: Folders containing sequences with detected wildfires are copied to an `annotations/` directory for further review.

## Usage

First, ensure you're in the `pyronear` conda environment with pyroengine installed:

```bash
conda activate pyronear
python plug_to_pyroengine.py --n 6 --max-gap 60 --conf-thresh 0.15
```

## Options

- `--images-dir`: Root images directory (defaults to `images/` next to the script)
- `--n`: Required number of consecutive images in a sequence (default: 6)
- `--max-gap`: Maximum allowed gap in seconds between consecutive images (default: 60)
- `--conf-thresh`: Confidence threshold for wildfire detection (default: 0.15)
- `--output-dir`: Output directory for detected sequences (default: `annotations/` next to images)

## Example

```bash
# Analyze sequences of 8 images with 30-second max gap and 0.20 confidence threshold
python plug_to_pyroengine.py --n 8 --max-gap 30 --conf-thresh 0.20 --output-dir ./detections
```

## Prerequisites for Detection

Before running wildfire detection, install pyroengine and its dependencies:

```bash
conda activate pyronear
cd ../../pyro-engine
pip install -r requirements.txt
pip install -e .
```

---


## Mécanisme de scraping (détail technique)

1. Le spider `scrappy_pyronear/spiders/alertwest_spider.py` :
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

2. Items (`scrappy_pyronear/items.py`) :
     - `PyronearItem` est un conteneur Scrapy standard définissant les champs attendus. Le pipeline et le spider s'appuient dessus pour transporter métadonnées + URL.

3. Pipeline `AlertwestImagePipeline` (`scrappy_pyronear/pipelines.py`) :
     - Hérite de `scrapy.pipelines.images.ImagesPipeline`.
     - Méthodes principales :
         - `open_spider(self, spider)` : initialise timers, compteurs et la barre de progression `tqdm`. Récupère `spider.total_cams` pour fixer la taille de la barre.
         - `get_media_requests(self, item, info)` :
             - Appelée pour chaque `item`. Si `item['image_url']` existe, elle met à jour la barre de progression puis retourne une `scrapy.Request` pointant vers l'URL d'image en transférant les métadonnées utiles via `meta` (ex : `id`, `azimuth`, `last_moved`).
             - Si l'URL est absente, incrémente un compteur `no_url`.
         - `media_failed(self, failure, request, info)` : intercepte les erreurs réseau/timout et incrémente des compteurs (`timeout_cam`, `failed_cam`) selon la nature de l'erreur.
         - `file_path(self, request, response=None, info=None, item=None)` : construit le chemin local de sauvegarde pour chaque image. Format : ``{cam_id}/{azimuth}/{cam_id}_{scraping_timestamp}.jpg`` (azimuth vaut `unknown` si absent).
         - `close_spider(self, spider)` : affiche un résumé (nombre d'échecs, d'URLs manquantes, temps écoulé) et ferme la barre de progression.

4. Réglages clés (`scrappy_pyronear/settings.py`) :
     - `FEEDS` : configuration pour exporter les métadonnées en JSON (`alertwest.json`).
     - Concurrence élevée pour maximiser le throughput : `CONCURRENT_REQUESTS = 64`, `CONCURRENT_REQUESTS_PER_DOMAIN = 32`, `CONCURRENT_ITEMS = 400`.
     - Timeout réduit pour favoriser la vitesse : `DOWNLOAD_TIMEOUT = 2` (modifiable via la ligne de commande `-s DOWNLOAD_TIMEOUT=3`).
     - `LOG_FORMATTER` personnalisé pour cacher les logs de timeout.
     - `RETRY_ENABLED = False` pour ne pas retenter les requêtes longues.