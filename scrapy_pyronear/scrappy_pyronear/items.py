"""Scrapy item definitions for AlertWest camera data."""

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class PyronearItem(scrapy.Item):
    """Item representing camera metadata and image URL."""

    id = scrapy.Field()
    name = scrapy.Field()
    azimuth = scrapy.Field()
    last_moved = scrapy.Field()
    image_url = scrapy.Field()
    valid_url = scrapy.Field()
