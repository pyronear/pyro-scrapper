"""Continuous scraping script for AlertWest.

This script launches the alertwest spider continuously with a configurable
interval between each execution.

Usage:
    python -m scrapy_pyronear.continuous_scraper [-s SETTING=VALUE]

To customize the interval and Raspberry Pi parameters, modify the values in config.py
"""

import argparse
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path
from scrapy_pyronear.config import (
    INTERVAL,
    N_RASPBERRY,
    RASPBERRY_ID,
    CYCLE_REFRESH_JSON,
    LAUNCH_WITH_CLEANING
)

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


class ContinuousScraper:
    """Class for continuous scraping of AlertWest."""

    def __init__(
        self, interval_seconds=30, n_raspberry=1, raspberry_id=0, cycle_refresh_json=1000, scrapy_settings=None
    ):
        """Initialize ContinuousScraper.

        Args:
            interval_seconds (int): Interval in seconds between each scraping
            n_raspberry (int): Total number of Raspberry Pi devices
            raspberry_id (int): ID of this Raspberry Pi
            cycle_refresh_json (int): Cycle number after which the JSON is refreshed
            scrapy_settings (dict): Scrapy settings to override

        """
        self.interval_seconds = INTERVAL
        self.n_raspberry = N_RASPBERRY
        self.raspberry_id = RASPBERRY_ID
        self.cycle_refresh_json = CYCLE_REFRESH_JSON
        self.scrapy_settings = scrapy_settings or {}
        self.running = True
        self.scrape_count = 0

        # Handle signals for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle stop signals (Ctrl+C, etc.)."""
        logger.info("Stop signal received. Stopping after the current cycle...")
        self.running = False

    def run_spider_once(self):
        """Launch the AlertWest spider once.

        Returns:
            bool: True if the spider ran successfully, False otherwise.

        """
        try:
            if LAUNCH_WITH_CLEANING :
                logger.info(f"🚀 Start of cleaning JSON and scraping cycle #{self.scrape_count}")

            else :
                self.scrape_count += 1
                logger.info(f"🚀 Start of scraping cycle #{self.scrape_count}")

            
            start_time = time.time()

            # Launch scrapy crawl in subprocess
            cmd = ["scrapy", "crawl", "alertwest"]
            cmd.extend(["-a", f"n_raspberry={self.n_raspberry}"])
            cmd.extend(["-a", f"raspberry_id={self.raspberry_id}"])
            cmd.extend(["-a", f"cycle_number={self.scrape_count}"])
            cmd.extend(["-a", f"cycle_refresh_json={self.cycle_refresh_json}"])

            # Add Scrapy settings
            for setting, value in self.scrapy_settings.items():
                cmd.extend(["-s", f"{setting}={value}"])

            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent,
                capture_output=False,  # Display output in real-time
                text=True,
            )

            elapsed_time = time.time() - start_time
            self.scrape_count += 1

            if result.returncode == 0:
                logger.info(f"✅ Cycle #{self.scrape_count} finished in {elapsed_time:.2f} seconds")
                return True
            else:
                logger.error(f"❌ Cycle #{self.scrape_count} failed with code {result.returncode}")
                return False

        except Exception as e:
            logger.error(f"❌ Error during scraping: {e}", exc_info=True)
            return False

    def run(self):
        """Run continuous scraping with the specified interval."""
        logger.info(f"🔄 Starting continuous scraping (interval: {self.interval_seconds}s)")
        logger.info(f"📡 Raspberry Pi configuration: ID {self.raspberry_id}/{self.n_raspberry - 1}")
        if self.scrapy_settings:
            settings_str = ", ".join([f"{k}={v}" for k, v in self.scrapy_settings.items()])
            logger.info(f"⚙️  Scrapy settings: {settings_str}")
        logger.info("Press Ctrl+C to stop gracefully")

        while self.running:
            cycle_start = time.time()

            # Launch a scraping cycle
            self.run_spider_once()

            # Calculate wait time before next cycle
            elapsed = time.time() - cycle_start
            wait_time = max(0, self.interval_seconds - elapsed)

            if wait_time > 0:
                logger.info(f"⏳ Waiting {wait_time:.2f}s before the next cycle...")

                # Wait time with ability to stop
                sleep_start = time.time()
                while (time.time() - sleep_start) < wait_time and self.running:
                    time.sleep(min(1, wait_time - (time.time() - sleep_start)))
            else:
                logger.warning(
                    f"⚠️  The cycle took {elapsed:.2f}s, longer than the interval of {self.interval_seconds}s"
                )

        logger.info(f"🛑 Stopping continuous scraping. Total cycles completed: {self.scrape_count}")


def main():
    """Parse command-line arguments and start continuous scraping."""
    parser = argparse.ArgumentParser(
        description="Continuous scraping script for AlertWest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples of usage:
  python continuous_scraper.py -s DOWNLOAD_TIMEOUT=3
        """,
    )

    parser.add_argument(
        "-s",
        action="append",
        dest="scrapy_settings",
        help="Scrapy settings to override (format: SETTING=value)",
    )

    args = parser.parse_args()

    # Validation
    if INTERVAL < 15:
        logger.error("Interval must be at least 15 seconds")
        sys.exit(1)

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

    # Launch continuous scraper
    scraper = ContinuousScraper(
        interval_seconds=INTERVAL,
        n_raspberry=N_RASPBERRY,
        raspberry_id=RASPBERRY_ID,
        scrapy_settings=scrapy_settings,
    )
    scraper.run()

if __name__ == "__main__":
    main()
