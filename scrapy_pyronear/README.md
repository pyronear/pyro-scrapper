## PIPELINE DE SCRAPPING D'IMAGES ALERTWEST

Pipeline de scraping d'images de caméras de surveillance du site alertwest.org pour l'entraînement d'un modèle de détection de départs de feu.

## Prérequis

- **Python 3.12.0**
- **Conda** ou **pip** pour la gestion des dépendances


## Installation

```bash
conda create --name pyronear python=3.12
conda activate pyronear
pip install -r requirements.txt
```

## Démarrage rapide

### Lancer le scraping

```bash
scrapy crawl alertwest
```

### Lancer avec paramètres personnalisés

```bash
scrapy crawl alertwest -s DOWNLOAD_TIMEOUT=3 CONCURRENT_ITEMS=100
```

### Paramètres disponibles cf `settings.py`

Exemples :

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `DOWNLOAD_TIMEOUT` | 2s | Délai maximal pour télécharger une image |
| `CONCURRENT_ITEMS` | 400 | Nombre d'items traités en parallèle dans la pipeline |
| `CONCURRENT_REQUESTS` | 64 | Nombre maximal de requêtes HTTP simultanées |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | 32 | Requêtes simultanées par domaine |


### Exporter les métadonnées en JSON

```bash
scrapy crawl alertwest -o alertwest.json
```

### Mode debug

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

## Architecture

```
scrappy_pyronear/
├── spiders/
│   └── alertwest_spider.py      # Spider principal
├── items.py                      # Définition des items
├── pipelines.py                  # Pipeline de téléchargement d'images
├── settings.py                   # Configuration Scrapy
└── logformatter.py               # Formatter personnalisé pour les logs
images/                           # Répertoire de sortie (généré)
tests/                            # Tests unitaires
alertwest.json                    # Export JSON des métadonnées (optionnel)
```

## Mécanisme de scraping

### 1. Spider (`alertwest_spider.py`)

- Envoie une requête GET vers l'API AlertWest.
- Parse la réponse JSON pour extraire :
  - `key_list` : mapping des clés courtes vers les noms de propriétés.
  - `data_cams` : liste des caméras.
- Mappe les propriétés intéressantes (Azimuth, camId, Screenshot, camLastMoved, etc.) vers leurs clés respectives.
- Pour chaque caméra, construit l'URL d'image au format :
  ```
  https://img.cdn.prod.alertwest.com/data/thumb/{cam_id}/{YYYY/MM/DD}/{img_name}
  ```
- Yield des items `PyronearItem` avec métadonnées et URL.

### 2. Items (`items.py`)

`PyronearItem` contient les champs :
- `id` : identifiant unique de la caméra
- `name` : nom de la caméra
- `azimuth` : orientation de la caméra
- `last_moved` : timestamp du dernier mouvement
- `image_url` : URL de l'image à télécharger
- `valid_url` : indicateur de validité de l'URL

### 3. Pipeline (`pipelines.py`)

Hérite de `scrapy.pipelines.images.ImagesPipeline` et :

| Méthode | Rôle |
|---------|------|
| `open_spider()` | Initialise les compteurs, timers et barre de progression |
| `get_media_requests()` | Génère les requêtes de téléchargement d'images en parallèle |
| `media_failed()` | Capture les erreurs (timeouts, connexions perdues) et met à jour les compteurs |
| `file_path()` | Définit la structure de stockage : `{cam_id}/{azimuth}/{cam_id}.jpg` |
| `close_spider()` | Affiche un résumé (échecs, URLs manquantes, temps écoulé) |

### 4. Optimisations de concurrence

- `CONCURRENT_REQUESTS = 64` : limite globale pour éviter de surcharger le réseau
- `CONCURRENT_REQUESTS_PER_DOMAIN = 32` : limite par domaine pour respecter les serveurs
- `CONCURRENT_ITEMS = 400` : traitement parallèle des items dans la pipeline
- `RETRY_ENABLED = False` : pas de retry sur les timeouts (gagne du temps)
- `DOWNLOAD_TIMEOUT = 2s` : timeout agressif pour favoriser la vitesse

### 5. Gestion des erreurs

Un `LogFormatter` personnalisé silencieux les logs de timeout pour garder une sortie propre. Les erreurs sont comptabilisées :
- **Timeouts** : images non téléchargées à cause du délai
- **Caméras down** : serveur a rejeté la requête (HTTP 4xx/5xx)
- **URLs manquantes** : paramètres manquants dans la réponse JSON

## Configuration

Tous les paramètres Scrapy se trouvent dans `settings.py`. Les principaux :

```python
CONCURRENT_REQUESTS = 64                    # Requêtes HTTP simultanées
CONCURRENT_ITEMS = 400                      # Items en parallèle
DOWNLOAD_TIMEOUT = 2                        # Timeout (secondes)
RETRY_ENABLED = False                       # Pas de retry
LOG_FORMATTER = "scrappy_pyronear.logformatter.SilentTimeoutLogFormatter"
```

## Exemple de sortie

```
Downloading images 🚀 : 100%|█████████████████████████████| 11702/11702 images

URL retrieved but camera is down for 1524 cameras among 11702 total cameras.
Miss a parameter in the json to construct URL for 999 cameras among 11702 total cameras.
Timed out for 45 cameras among 11702 total cameras.
Time taken: 2.53 minutes
```

## Dépannage

### Scraping lent

Augmentez les paramètres de concurrence :
```bash
scrapy crawl alertwest -s CONCURRENT_REQUESTS=128 CONCURRENT_ITEMS=500
```

### Trop de timeouts

Augmentez le délai :
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
             `https://img.cdn.prod.alertwest.com/data/thumb/{cam_id}/{YYYY/MM/DD}/{img_name}` (la date utilisée est la date courante).
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
         - `file_path(self, request, response=None, info=None, item=None)` : construit le chemin local de sauvegarde pour chaque image. Format : ``{cam_id}/{azimuth}/{cam_id}.jpg`` (azimuth vaut `unknown` si absent).
         - `close_spider(self, spider)` : affiche un résumé (nombre d'échecs, d'URLs manquantes, temps écoulé) et ferme la barre de progression.

4. Réglages clés (`scrappy_pyronear/settings.py`) :
     - `FEEDS` : configuration pour exporter les métadonnées en JSON (`alertwest.json`).
     - Concurrence élevée pour maximiser le throughput : `CONCURRENT_REQUESTS = 64`, `CONCURRENT_REQUESTS_PER_DOMAIN = 32`, `CONCURRENT_ITEMS = 400`.
     - Timeout réduit pour favoriser la vitesse : `DOWNLOAD_TIMEOUT = 2` (modifiable via la ligne de commande `-s DOWNLOAD_TIMEOUT=3`).
     - `LOG_FORMATTER` personnalisé pour cacher les logs de timeout.
     - `RETRY_ENABLED = False` pour ne pas retenter les requêtes longues.