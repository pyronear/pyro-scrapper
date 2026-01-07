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

### Quick start

```bash
# Default interval (60s)
python continuous_scraper.py

# Custom interval (e.g., 90s)
python continuous_scraper.py --interval 90

# With Raspberry Pi distribution
python continuous_scraper.py --interval 60 --n_raspberry 2 --raspberry_id 0

# With Scrapy settings override
python continuous_scraper.py --interval 60 -s DOWNLOAD_TIMEOUT=3 -s CONCURRENT_ITEMS=100

# Combined: Raspberry Pi + Scrapy settings
python continuous_scraper.py --interval 60 --n_raspberry 2 --raspberry_id 1 -s DOWNLOAD_TIMEOUT=3 -s CONCURRENT_ITEMS=100
```

Notes
- Graceful stop: press Ctrl+C; the current cycle finishes, then the runner exits.
- If a cycle takes longer than the interval, the next cycle starts immediately after.
- Outputs: `alertwest.json` is overwritten each cycle (per `settings.py`), and images are saved under `images/`.

## One‑off crawl (single run)

```bash
scrapy crawl alertwest
```

### Run with multiple raspberry pis

Parameters :
- `n_raspberry` : total number of raspberry pis
- `raspberry_id` : the id of the raspberry running the code starting from 0, if there are 2 raspberries and this is the first one, the ID is 0.

For example, with 2 raspberries and the first one is running :

```bash
scrapy crawl alertwest -a n_raspberry=2 -a raspberry_id=0
```
### Run with custom parameters

```bash
scrapy crawl alertwest -s DOWNLOAD_TIMEOUT=3 CONCURRENT_ITEMS=100
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

## Project structure

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

## How it works

### 1) Spider (`alertwest_spider.py`)

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

### 2) Items (`items.py`)

`PyronearItem` fields:
- `id`: camera identifier
- `name`: camera name
- `azimuth`: camera orientation
- `last_moved`: last movement timestamp
- `image_url`: image URL to download
- `valid_url`: URL validity flag

### 3) Pipeline (`pipelines.py`)

Inherits from `scrapy.pipelines.images.ImagesPipeline` and:

| Method | Purpose |
|--------|---------|
| `open_spider()` | Initializes counters, timers, and a progress bar |
| `get_media_requests()` | Generates parallel image download requests |
| `media_failed()` | Captures errors (timeouts, connection issues) and updates counters |
| `file_path()` | Storage structure: `{cam_id}/{azimuth}/{cam_id}_{scraping_timestamp}.jpg` |
| `close_spider()` | Prints a summary (failures, missing URLs, elapsed time) |

### 4) Concurrency tuning

- `CONCURRENT_REQUESTS = 64`: avoid overwhelming the network
- `CONCURRENT_REQUESTS_PER_DOMAIN = 32`: be polite to the remote host
- `CONCURRENT_ITEMS = 400`: speed up pipeline processing
- `RETRY_ENABLED = False`: skip retries for faster throughput
- `DOWNLOAD_TIMEOUT = 2s`: aggressive timeout for speed (tune as needed)

### 5) Error handling

A custom `LogFormatter` silences timeout noise. Counters track:
- Timeouts: images not downloaded due to deadlines
- Camera down: HTTP 4xx/5xx
- Missing URLs: incomplete JSON preventing URL construction

### 6) Image storage structure

```
images/
└── {cam_id}/
      └── {azimuth}/
            └── {cam_id}_{scraping_timestamp}.jpg
```

## Configuration

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