"""Item definitions for Scrappy Pyronear."""

import scrapy


class PyronearItem(scrapy.Item):
    """Scraped camera metadata."""

    id = scrapy.Field()
    name = scrapy.Field()
    azimuth = scrapy.Field()
    last_moved = scrapy.Field()
    image_url = scrapy.Field()
    valid_url = scrapy.Field()
