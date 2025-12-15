# Pyronear
Pipeline de scrapping d'images de caméras de surveillance pour entrainement d'un modèle de détection de départs de feu.

### Commande pour se placer dans le bon dossier 

```
cd Pyronear
```

### Lancer le scrapping des images 

```
scrapy crawl alertwest
```

### Utiliser les paramètres pour ajuster le scrapping

```
scrapy crawl alertwest -s
    DOWNLOAD_TIMEOUT=3 # Temps maximum (en secondes) pour télécharger une image
    CONCURRENT_ITEMS=100 # Nombre d'items traités en parallèle
```

### Lancer le scrapping des images ET enregistrement du json 

```
scrapy crawl alertwest -o alertwest.json
```
## Lancer les tests 

```
pytest -v .\test\test_alertwest_spider.py
```

## Lancer en mode debug

```
scrapy crawl alertwest -s LOG_LEVEL=DEBUG
```

## Structure du dépôt

Ce dépôt contient un mini-projet Scrapy pour récupérer des images issues de l'API AlertWest et les stocker localement pour l'entraînement.

- `scrappy_pyronear/` : package Scrapy principal
    - `spiders/alertwest_spider.py` : spider qui interroge l'API AlertWest, parse le JSON et yield des items (`PyronearItem`).
    - `items.py` : définition de l'item `PyronearItem` (champs : `id`, `name`, `azimuth`, `last_moved`, `image_url`, `valid_url`).
    - `pipelines.py` : pipeline `AlertwestImagePipeline` qui télécharge les images, gère la progression et les erreurs, et crée l'arborescence de stockage.
    - `settings.py` : réglages Scrapy (concurrency, timeouts, export JSON, log formatter, etc.).
- `images/` : répertoire de destination (généré par le pipeline) contenant les dossiers par `cam_id` et `azimuth`.
- `alertwest.json` : export JSON possible des métadonnées (via le feed ou option `-o`).
- `tests/` : tests unitaires.

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