"""Scrapy pipelines for AlertWest scraper."""

import os
import time
import json
import requests
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import scrapy
from scrapy.pipelines.images import ImagesPipeline
from twisted.internet.defer import TimeoutError as DeferTimeoutError
from twisted.internet.error import TCPTimedOutError, TimeoutError
from twisted.web.client import ResponseNeverReceived


class FilteredIdsPipeline:
    """
        ASSOCIATED SPIDER: spider_filtered_ids
        
        Responsibilities:
            - Filter cameras based on multiple criteria
            - Collect statistics about filtered cameras
            - Save valid camera IDs to good_ids.json
        
        Process:
            1. Count each filter result (thermal, dot, offline, etc.)
            2. Aggregate valid IDs
            3. Save to good_ids.json on spider close
        """

    def __init__(self):
        self.output_file = Path(__file__).parent.parent / "good_ids.json"
        self.good_ids = {"ids": []}

    def open_spider(self, spider):
        """Initialize pipeline when spider opens."""
        self.time = time.time()
        self.progress_bar = None
        # Counters for statistics
        self.stats = {"thermal":0, "dot":0, "offline":0, "missing_informations":0, "low_res":0, "total":0}
        

    def close_spider(self, spider):
        """Save collected IDs to JSON file when spider closes."""
        if self.progress_bar:
            self.progress_bar.close()
        print(f"\n Unkeeped {self.stats['thermal']} thermal cameras"
            f"{self.stats['dot']} DOT cameras,"
            f"{self.stats['offline']} offline cameras,"
            f"{self.stats['missing_informations']} missing information cameras,"
            f"{self.stats['low_res']} low-resolution cameras"
        )
        with open(self.output_file, "w") as f:
            json.dump(self.good_ids, f, indent=2)
        print(f"Saved {len(self.good_ids['ids'])} camera  among {self.stats['total']} total cameras to {self.output_file}.")

    def process_item(self, item, spider):
        """Process item and apply filters."""
        
        if self.progress_bar is None:
            self.total = spider.total_cams
            self.progress_bar = tqdm(
                total=self.total,
                desc="Filtering cameras 🚀 ",
                bar_format="{l_bar}\033[92m{bar}\033[0m| {n_fmt}/{total_fmt} images",
                unit="image",
            )
            return item

        self.stats["total"] += 1

        is_valid = True

        if "thermal" in item.get("name").lower():
            self.stats["thermal"] += 1
            is_valid = False
        if "dot" in item.get("provider").lower():
            self.stats["dot"] += 1
            is_valid = False
        if item.get("offline") == 1:
            self.stats["offline"] += 1
            is_valid = False
        if not item.get("id") or not item.get("Screenshot"):
            self.stats["missing_informations"] += 1
            is_valid = False
            
        date_for_path = datetime.now().strftime("%Y/%m/%d")
        image_url=(
                    f"https://img.cdn.prod.alertwest.com/data/img/"
                    f"{item.get('id')}/{date_for_path}/"
                    f"{item.get('Screenshot')}"
                )
        if self._get_image_metadata(image_url) < 640:
            self.stats["low_res"] += 1
            is_valid = False

        if is_valid:
            # All tests passed, add to good_ids
            self.good_ids["ids"].append(item.get("id"))
            
        self.progress_bar.update(1)
        return item

    @staticmethod
    def _get_image_metadata(image_url):
        """Fetch only image metadata (headers) without downloading the full image."""
        response = requests.head(image_url, timeout=1, allow_redirects=True)
        response.raise_for_status()
        
        # Get image size from Content-Length header
        content_length = response.headers.get("Content-Length")
        
        return int(content_length)
    


class GetImagesPipeline(ImagesPipeline):
    """
        ASSOCIATED SPIDER: spider_get_images
        
        Responsibilities:
            - Generate download requests for camera images
            - Download images from AlertWest servers
            - Save images to disk with proper directory structure
        
        Process:
            1. Receive items with image_url
            2. Generate scrapy.Request for each image
            3. Download image via Scrapy downloader
            4. Save to disk using file_path()
        """


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.images_dir = None

    def open_spider(self, spider):
        """Initialize pipeline when spider opens."""
        self.progress_bar = None
        self.timeout_cam = 0
        
    def close_spider(self, spider):
        """Finalize pipeline when spider closes."""
        if self.progress_bar:
            self.progress_bar.close()
        print(f"Timed out for {self.timeout_cam} cameras among {spider.total_cams_to_get_image_of} total cameras.")
       
    def get_media_requests(self, item, info):
        """Download and save image."""
        
        if self.progress_bar is None:
            self.total = info.spider.total_cams_to_get_image_of
            self.progress_bar = tqdm(
                total=self.total,
                desc="Downloading images 🚀 ",
                bar_format="{l_bar}\033[92m{bar}\033[0m| {n_fmt}/{total_fmt} images",
                unit="image",
            )
            
            
        date_for_path = datetime.now().strftime("%Y/%m/%d")
        image_url=(
                    f"https://img.cdn.prod.alertwest.com/data/img/"
                    f"{item.get('id')}/{date_for_path}/"
                    f"{item.get('Screenshot')}"
                )
        
        scraped_at = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        yield scrapy.Request(
            image_url,
            meta={
                "id": item["id"],
                "azimuth": item["azimuth"],
                "scraped_at": scraped_at,
            },
        )

        return item
    
    def item_completed(self, results, item, info):
        """Update progress bar after each item is processed."""
        self.progress_bar.update(1)
        return item
    
    def media_failed(self, failure, request, info):
        """Handle failed media downloads and count error types."""
        # Count timeouts separately, silence their log via custom LogFormatter
        if failure.check(TimeoutError, TCPTimedOutError, ResponseNeverReceived, DeferTimeoutError):
            self.timeout_cam += 1
        return None

    def file_path(self, request, response=None, info=None, item=None):
        """Determine the file path for saving downloaded images."""
        meta = request.meta
        cam_id = item.get("id")

        # If there is no azimuth, it is replaced by unknown
        azimuth = item.get("azimuth") or "unknown"
        scraped_at = meta.get("scraped_at") or "unknown"
        filename = f"{cam_id}_{scraped_at}.jpg"

        return os.path.join(cam_id, azimuth, filename)
