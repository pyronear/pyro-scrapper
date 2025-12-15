# Scrapy settings for pyronear project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "scrapping_pyronear"

SPIDER_MODULES = ["scrappy_pyronear.spiders"]
NEWSPIDER_MODULE = "scrappy_pyronear.spiders"

# Définir les exports de données
FEEDS = {
    "alertwest.json": {
        "format": "json",
        "encoding": "utf8",
        "store_empty": False,
        "indent": 2,
        "overwrite": True
    }
}

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = "pyronear (+http://www.yourdomain.com)"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests performed by Scrapy (default: 16)
# Increase these values to parallelize downloads. Tune according to your
# network bandwidth and target server politeness (and robots.txt).
CONCURRENT_REQUESTS = 64

# The maximum number of concurrent requests that will be performed to any
# single domain. Keep this lower than CONCURRENT_REQUESTS to avoid overloading
# the remote host.
CONCURRENT_REQUESTS_PER_DOMAIN = 32

# If you prefer limiting by IP instead of domain, set CONCURRENT_REQUESTS_PER_IP.
# Leave as 0 to disable IP-based limits.
CONCURRENT_REQUESTS_PER_IP = 0

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 0
# The download delay setting will honor only one of:
# Increase the number of pipeline items processed in parallel
CONCURRENT_ITEMS = 400

# Increase Twisted threadpool size for blocking calls (DNS resolution, etc.)
REACTOR_THREADPOOL_MAXSIZE = 20

# Enable DNS cache to reduce DNS lookups
DNSCACHE_ENABLED = True

# Disable AutoThrottle when you want maximum throughput. If you need to be
# polite to the remote host, consider enabling AutoThrottle instead.
AUTOTHROTTLE_ENABLED = False

# Download timeout (seconds)
DOWNLOAD_TIMEOUT = 2
LOG_FORMATTER = "scrappy_pyronear.logformatter.SilentTimeoutLogFormatter" # Custom log formatter to silence timeout errors

# Disable retries to avoid waiting time on servers that don't respond
RETRY_ENABLED = False


# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    "pyronear.middlewares.PyronearSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#DOWNLOADER_MIDDLEWARES = {
#    "pyronear.middlewares.PyronearDownloaderMiddleware": 543,
#}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
#ITEM_PIPELINES = {
#    "pyronear.pipelines.PyronearPipeline": 300,
#}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
#AUTOTHROTTLE_ENABLED = True
# The initial download delay
#AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
#AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
# FEED_EXPORT_ENCODING = "utf-8"

# Article pipeline order and priority. 0 means high priority, 1000 means low priority.
ITEM_PIPELINES = {
    'scrappy_pyronear.pipelines.AlertwestImagePipeline': 300,
}

IMAGES_STORE = 'images'
LOG_ENABLED = True
LOG_LEVEL = "ERROR"