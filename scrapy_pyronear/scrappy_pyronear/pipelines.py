"""Scrapy pipelines for image downloading."""

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface

import os
import time
from datetime import datetime

import scrapy
from scrapy.pipelines.images import ImagesPipeline
from tqdm import tqdm
from twisted.internet.defer import TimeoutError as DeferTimeoutError
from twisted.internet.error import TCPTimedOutError, TimeoutError
from twisted.web.client import ResponseNeverReceived


class AlertwestImagePipeline(ImagesPipeline):
    """Scrapy pipeline for downloading camera images.

    This pipeline:
    - Downloads images from camera URLs provided in items.
    - Tracks download progress using a tqdm progress bar.
    - Handles various failure cases, including timeouts, missing URLs, and cameras that are down.
    - Maintains counters for failed downloads, missing URLs, and timeouts, and reports them when the spider closes.
    """

    def open_spider(self, spider):
        """Initialize pipeline when spider opens."""
        self.time = time.time()
        self.spiderinfo = self.SpiderInfo(spider)
        self.total = getattr(spider, "total_relevant_cams", 0)
        self.failed_cam = 0  # counter for failed downloads
        self.timeout_cam = 0  # compteur des timeouts
        self.progress_bar = None

    def close_spider(self, spider):
        """Print summary statistics when spider closes."""
        print(f"\nURL retrieved but camera is down for {self.failed_cam} cameras among {self.total} total cameras.")
        print(f"Timed out for {self.timeout_cam} cameras among {self.total} total cameras.")
        print(f"Time taken: {(time.time() - self.time) / 60:.2f} minutes")
        if self.progress_bar:
            self.progress_bar.close()

    def get_media_requests(self, item, info):
        """Generate Scrapy requests to download images, passing camera metadata.

        Args:
            item (dict): Dictionary containing image and camera metadata. Expected keys:
                - image_url (str): URL of the image to download.
                - id (str/int): Unique identifier for the camera.
                - azimuth (str/int): Azimuth value of the camera.
                - last_moved (str): Timestamp of the last movement.
            info: Scrapy pipeline info object.

        Yields:
            scrapy.Request: For each valid image URL, yields a request with metadata in the `meta` dict:
                - id
                - azimuth
                - last_moved

        Side effects:
            Updates progress bar and counters for missing URLs.

        """
        if self.progress_bar is None:
            self.total = info.spider.total_relevant_cams
            self.progress_bar = tqdm(
                total=self.total,
                desc="Downloading images 🚀 ",
                bar_format="{l_bar}\033[92m{bar}\033[0m| {n_fmt}/{total_fmt} images",
                unit="image",
            )

        url = item["image_url"]
        self.progress_bar.update(1)
        scraped_at = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        yield scrapy.Request(
            url,
            meta={
                "id": item["id"],
                "azimuth": item["azimuth"],
                "last_moved": item.get("last_moved"),
                "scraped_at": item.get("scraped_at", scraped_at),
            },
        )

    def media_failed(self, failure, request, info):
        """Handle failed media downloads and count error types."""
        # Count timeouts separately, silence their log via custom LogFormatter
        if failure.check(TimeoutError, TCPTimedOutError, ResponseNeverReceived, DeferTimeoutError):
            self.timeout_cam += 1
            return None
        self.failed_cam += 1
        return None

    def file_path(self, request, response=None, info=None, item=None):
        """Determine the file path for saving downloaded images."""
        meta = request.meta
        cam_id = str(item.get("id"))

        # If there is no azimuth, it is replaced by unknown
        azimuth = str(item.get("azimuth") or "unknown")
        scraped_at = str(meta.get("scraped_at") or "unknown")
        filename = f"{cam_id}_{scraped_at}.jpg"

        return os.path.join(cam_id, azimuth, filename)
