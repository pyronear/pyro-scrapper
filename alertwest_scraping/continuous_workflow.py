"""Continuous workflow script for inference and scraping.

This script manages a 24-hour workflow:
- Night: Run inference on collected images
- Day: Scrape camera images with Raspberry Pi load balancing

Usage:
    python -m alertwest_scraping.continuous_workflow [-s SETTING=VALUE]
"""

import argparse
import json
import logging
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astral import LocationInfo
from astral.sun import sun

from alertwest_scraping.config import (
    CACHE_DIR,
    INTERVAL,
    MAX_GAP_SECONDS,
    MIN_DETECTIONS,
    N_CONSECUTIVE,
    N_RASPBERRY,
    RASPBERRY_ID,
)
from alertwest_scraping.orchestration_inference_send_annotation_api import (
    run_inference_pipeline,
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ContinuousWorkflow:
    """Class for continuous workflow management (inference + scraping)."""

    def __init__(
        self,
        force_get_scrapping_ids=False,
        scrapy_settings=None,
    ):
        """Initialize ContinuousWorkflow.

        Args:
            force_get_scrapping_ids (bool): Force re-scraping of camera IDs
            scrapy_settings (dict): Scrapy settings to override

        """
        self.interval = INTERVAL
        self.n_raspberry = N_RASPBERRY
        self.raspberry_id = RASPBERRY_ID
        self.force_get_scrapping_ids = force_get_scrapping_ids
        self.scrapy_settings = scrapy_settings or {}
        self.running = True
        self.inference_done = False
        self.cycle_count = 0
        self.scrape_count = 0
        self.good_ids_path = Path(__file__).parent / "good_ids.json"
        self.images_dir = Path(__file__).parent / "images"
        self.n_consecutive = N_CONSECUTIVE
        self.max_gap_seconds = MAX_GAP_SECONDS
        self.min_detections = MIN_DETECTIONS
        # Salt Lake City location for sun calculations
        self.location = LocationInfo(
            name="SaltLakeCity",
            region="USA",
            timezone="America/Denver",
            latitude=40.7608,
            longitude=-111.8910,
        )

        # Handle signals for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle stop signals (Ctrl+C, etc.)."""
        logger.info("Stop signal received. Stopping after the current cycle...")
        # self.running = False
        # Pour le debugging
        sys.exit(0)

    def is_night(self):
        """Check if it's currently night at the central US location."""
        if isinstance(self.location.timezone, str):
            try:
                tz = ZoneInfo(self.location.timezone)
            except ZoneInfoNotFoundError:
                logger.error(
                    "Timezone data not found for '%s'. Install 'tzdata' to fix this. Falling back to UTC.",
                    self.location.timezone,
                )
                tz = timezone.utc
        else:
            tz = self.location.timezone
        now = datetime.now(tz=tz)
        s = sun(self.location.observer, date=now.date(), tzinfo=tz)
        return now < s["sunrise"] or now > s["sunset"]

    def run_spider_filtered_ids(self):
        """Launch the spider_filtered_ids spider to collect all camera IDs."""
        try:
            logger.info("🕵️  Running spider_filtered_ids to fetch all camera IDs...")
            cmd = ["scrapy", "crawl", "spider_filtered_ids"]

            for setting, value in self.scrapy_settings.items():
                cmd.extend(["-s", f"{setting}={value}"])

            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent,
                capture_output=False,
                text=True,
            )

            if result.returncode == 0:
                logger.info("✅ spider_filtered_ids completed successfully")
                return True
            else:
                logger.error(f"❌ spider_filtered_ids failed with code {result.returncode}")
                return False

        except Exception as e:
            logger.error(f"❌ Error running spider_filtered_ids: {e}", exc_info=True)
            return False

    def split_camera_ids(self, camera_ids):
        """Split cameras across Raspberry Pi instances.

        Args:
            camera_ids (list): List of all camera IDs

        Returns:
            list: Subset of camera IDs for this Raspberry Pi

        """
        splitted_for_me = []

        for rid in range(self.n_raspberry):
            subset = [cam for idx, cam in enumerate(camera_ids) if idx % self.n_raspberry == rid]

            with open(CACHE_DIR / f"alertwest_split_raspberry_{rid}.json", "w") as f:
                json.dump(subset, f)

            if rid == self.raspberry_id:
                splitted_for_me = subset

        logger.info(f"📡 Assigned {len(splitted_for_me)} cameras to Raspberry Pi {self.raspberry_id}")
        return splitted_for_me

    def run_spider_get_images(self, camera_ids):
        """Launch spider_get_images with the assigned camera IDs.

        Args:
            camera_ids (list): List of camera IDs to scrape for this Raspberry Pi

        """
        try:
            logger.info(f"📸 Running spider_get_images with {len(camera_ids)} cameras...")
            cmd = ["scrapy", "crawl", "spider_get_images"]
            cmd.extend(["-a", f"n_raspberry={self.n_raspberry}"])
            cmd.extend(["-a", f"raspberry_id={self.raspberry_id}"])
            cmd.extend(["-a", f"camera_ids={json.dumps(camera_ids)}"])

            for setting, value in self.scrapy_settings.items():
                cmd.extend(["-s", f"{setting}={value}"])

            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent,
                capture_output=False,
                text=True,
            )

            if result.returncode == 0:
                logger.info("✅ spider_get_images completed successfully")
                return True
            else:
                logger.error(f"❌ spider_get_images failed with code {result.returncode}")
                return False

        except Exception as e:
            logger.error(f"❌ Error running spider_get_images: {e}", exc_info=True)
            return False

    def cleanup_images(self):
        """Delete all downloaded images from the images directory."""
        try:
            if self.images_dir.exists():
                shutil.rmtree(self.images_dir)
                logger.info(f"✅ Cleaned up all images from {self.images_dir}")
            else:
                logger.info("ℹ️  No images directory found to clean")
        except Exception as e:
            logger.error(f"❌ Error cleaning up images: {e}", exc_info=True)

    def run_inference(self):
        """Run inference on collected images during night hours.

        This function executes the pyroengine inference pipeline on all collected
        images, detecting fire sequences and saving results to the annotations directory.
        """
        logger.info("🌙 Starting inference phase...")

        if not self.images_dir.exists():
            logger.warning(f"⚠️  No images directory found at {self.images_dir}")
            self.cleanup_images()
            self.inference_done = True
            return

        try:
            # Run the inference pipeline
            total_detections = run_inference_pipeline(
                images_dir=self.images_dir,
                n_consecutive=self.n_consecutive,
                max_gap_seconds=self.max_gap_seconds,
                min_detections=self.min_detections,
                logger=logger,
            )

            logger.info(f"✅ Inference phase completed - {total_detections} detection(s) found")
        except Exception as e:
            logger.error(f"❌ Error during inference: {e}", exc_info=True)

        # Cleanup images after inference
        self.cleanup_images()
        self.inference_done = True

    def run_scraping_cycle(self, camera_ids):
        """Run a single scraping cycle for images with wait time.

        Args:
            camera_ids (list): List of camera IDs to scrape

        """
        logger.info(f"🚀 Start of scraping cycle #{self.scrape_count}")

        cycle_start = time.time()
        self.run_spider_get_images(camera_ids)
        self.scrape_count += 1
        elapsed_time = time.time() - cycle_start

        logger.info(f"✅ Cycle #{self.scrape_count} finished in {elapsed_time:.2f} seconds")

        # Calculate wait time
        elapsed = time.time() - cycle_start
        wait_time = max(0, 30 - elapsed)

        if wait_time > 0:
            logger.info(f"⏳ Waiting {wait_time:.2f}s before next scrape...")
            sleep_start = time.time()
            while (time.time() - sleep_start) < wait_time and self.running and not self.is_night():
                time.sleep(min(1, wait_time - (time.time() - sleep_start)))

    def run(self):
        """Run continuous 24-hour workflow."""
        logger.info("🔄 Starting continuous workflow")
        logger.info(f"📡 Raspberry Pi configuration: ID {self.raspberry_id}/{self.n_raspberry - 1}")
        if self.scrapy_settings:
            settings_str = ", ".join([f"{k}={v}" for k, v in self.scrapy_settings.items()])
            logger.info(f"⚙️  Scrapy settings: {settings_str}")
        logger.info("Press Ctrl+C to stop gracefully")

        while self.running:
            while self.is_night():
                if not self.inference_done:
                    logger.info("🌙 Night phase detected - Running inference")
                    self.run_inference()
                else:
                    logger.info("💤 Inference already done, waiting for day phase...")
                    time.sleep(1800)  # Sleep for 30 minutes

            if not self.running:
                break

            while self.running and not self.is_night():
                # Reset inference flag at the start of daytime
                if self.inference_done:
                    logger.info("🔄 New day cycle started - Resetting inference flag and cleaning images")
                    self.cleanup_images()
                    self.inference_done = False
                    self.cycle_count = 0

                # Check if good_ids.json exists
                if not self.good_ids_path.exists() or self.force_get_scrapping_ids:
                    if self.force_get_scrapping_ids:
                        logger.info("🔄 Force re-scraping camera IDs...")
                    else:
                        logger.info("📄 good_ids.json not found, fetching camera IDs...")

                    self.run_spider_filtered_ids()

                # Load good_ids.json and split across Raspberry Pis
                if self.good_ids_path.exists():
                    with open(self.good_ids_path, "r") as f:
                        good_ids_data = json.load(f)
                    camera_ids = good_ids_data.get("ids", [])

                    if camera_ids:
                        assigned_ids = self.split_camera_ids(camera_ids)

                        # Run scraping cycles while it's still day
                        while self.running and not self.is_night():
                            self.run_scraping_cycle(assigned_ids)
                            self.cycle_count += 1

                        logger.info(f"🌅 Daytime scraping phase ended after {self.cycle_count} cycles")
                    else:
                        logger.warning("⚠️  No camera IDs found in good_ids.json")
                        time.sleep(60)
                else:
                    logger.error("❌ good_ids.json not found after spider execution")
                    time.sleep(60)

        logger.info(f"🛑 Stopping continuous workflow. Total scraping cycles: {self.scrape_count}")


def main():
    """Parse command-line arguments and start continuous workflow."""
    parser = argparse.ArgumentParser(
        description="Continuous workflow for inference and scraping",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples of usage:
  python continuous_workflow.py -s DOWNLOAD_TIMEOUT=3
  python continuous_workflow.py --force-scrape
        """,
    )

    parser.add_argument(
        "-s",
        action="append",
        dest="scrapy_settings",
        help="Scrapy settings to override (format: SETTING=value)",
    )

    parser.add_argument(
        "--force-scrape",
        action="store_true",
        dest="force_scrape",
        help="Force re-scraping of camera IDs even if good_ids.json exists",
    )

    args = parser.parse_args()

    # Validate Raspberry Pi parameters
    if RASPBERRY_ID >= N_RASPBERRY:
        logger.error(
            f"Invalid Raspberry Pi configuration: raspberry_id ({RASPBERRY_ID}) "
            f"must be less than n_raspberry ({N_RASPBERRY})"
        )
        sys.exit(1)

    # Parse Scrapy settings
    scrapy_settings = {}
    if args.scrapy_settings:
        for setting in args.scrapy_settings:
            if "=" in setting:
                key, value = setting.split("=", 1)
                scrapy_settings[key] = value

    # Launch workflow
    workflow = ContinuousWorkflow(
        force_get_scrapping_ids=args.force_scrape,
        scrapy_settings=scrapy_settings,
    )
    workflow.run()


if __name__ == "__main__":
    main()
