"""Script de scraping continu pour AlertWest.

Ce script lance la spider alertwest de manière continue avec un intervalle
configurable entre chaque exécution.

Usage:
    python continuous_scraper.py [--interval SECONDS] [--n_raspberry N] [--raspberry_id ID] [-s SETTING=VALUE]

Options:
    --interval SECONDS      Intervalle en secondes entre chaque scraping (défaut: 60)
    --n_raspberry N         Nombre total de Raspberry Pi (défaut: 1)
    --raspberry_id ID       ID de ce Raspberry Pi (défaut: 0)
    -s SETTING=VALUE        Settings Scrapy à surcharger (ex: DOWNLOAD_TIMEOUT=3, CONCURRENT_ITEMS=100)

Exemples:
    python continuous_scraper.py --interval 60
    python continuous_scraper.py --interval 60 --n_raspberry 2 --raspberry_id 0
    python continuous_scraper.py --interval 60 --n_raspberry 2 --raspberry_id 1 -s DOWNLOAD_TIMEOUT=3 -s CONCURRENT_ITEMS=100
"""

import argparse
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path

# Configuration du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


class ContinuousScraper:
    """Gestionnaire de scraping continu."""

    def __init__(self, interval_seconds=30, n_raspberry=1, raspberry_id=0, scrapy_settings=None):
        """Initialise le scraper continu.

        Args:
            interval_seconds (int): Interval en secondes entre chaque scraping
            n_raspberry (int): Nombre total de Raspberry Pi
            raspberry_id (int): ID de ce Raspberry Pi
            scrapy_settings (dict): Settings Scrapy à surcharger

        """
        self.interval_seconds = interval_seconds
        self.n_raspberry = n_raspberry
        self.raspberry_id = raspberry_id
        self.scrapy_settings = scrapy_settings or {}
        self.running = True
        self.scrape_count = 0
        

        # Gestion des signaux pour arrêt propre
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle stop signals (Ctrl+C, etc.)."""
        logger.info("Stop signal received. Stopping after the current cycle...")
        self.running = False

    def run_spider_once(self):
        """Lance la spider une seule fois via subprocess.

        Returns:
            bool: True si le scraping s'est bien déroulé, False sinon

        """
        try:
            logger.info(f"🚀 Start of scraping cycle #{self.scrape_count + 1}")
            start_time = time.time()

            # Lance scrapy crawl en subprocess
            cmd = ["scrapy", "crawl", "alertwest"]
            cmd.extend(["-a", f"n_raspberry={self.n_raspberry}"])
            cmd.extend(["-a", f"raspberry_id={self.raspberry_id}"])
            
            # Add Scrapy settings
            for setting, value in self.scrapy_settings.items():
                cmd.extend(["-s", f"{setting}={value}"])
            
            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent,
                capture_output=False,  # Affiche la sortie en temps réel
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
        logger.info(f"📡 Raspberry Pi configuration: ID {self.raspberry_id}/{self.n_raspberry}")
        if self.scrapy_settings:
            settings_str = ", ".join([f"{k}={v}" for k, v in self.scrapy_settings.items()])
            logger.info(f"⚙️  Scrapy settings: {settings_str}")
        logger.info("Press Ctrl+C to stop gracefully")

        while self.running:
            cycle_start = time.time()

            # Lance un cycle de scraping
            self.run_spider_once()

            # Calcule le temps d'attente avant le prochain cycle
            elapsed = time.time() - cycle_start
            wait_time = max(0, self.interval_seconds - elapsed)

            if wait_time > 0:
                logger.info(f"⏳ Waiting {wait_time:.2f}s before the next cycle...")

                # Temps d'attente avec possibilité d'arrêt
                sleep_start = time.time()
                while (time.time() - sleep_start) < wait_time and self.running:
                    time.sleep(min(1, wait_time - (time.time() - sleep_start)))
            else:
                logger.warning(
                    f"⚠️  The cycle took {elapsed:.2f}s, longer than the interval of {self.interval_seconds}s"
                )

        logger.info(f"🛑 Stopping continuous scraping. Total cycles completed: {self.scrape_count}")


def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(
        description="Continuous scraping script for AlertWest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples of usage:
  python continuous_scraper.py                                        # Default interval (60s)
  python continuous_scraper.py --interval 90                          # Every 90 seconds
  python continuous_scraper.py --interval 60 --n_raspberry 2 --raspberry_id 0
  python continuous_scraper.py --interval 60 -s DOWNLOAD_TIMEOUT=3 -s CONCURRENT_ITEMS=100
  python continuous_scraper.py --interval 60 --n_raspberry 2 --raspberry_id 1 -s DOWNLOAD_TIMEOUT=3
        """,
    )

    parser.add_argument(
        "--interval", type=int, default=60, help="Interval in seconds between each scraping (default: 60)"
    )
    
    parser.add_argument(
        "--n_raspberry",
        type=int,
        default=1,
        help="Total number of Raspberry Pi devices (default: 1)",
    )
    
    parser.add_argument(
        "--raspberry_id",
        type=int,
        default=0,
        help="ID of this Raspberry Pi, starting from 0 (default: 0)",
    )
    
    parser.add_argument(
        "-s",
        action="append",
        dest="scrapy_settings",
        help="Scrapy settings to override (format: SETTING=value)",
    )

    args = parser.parse_args()

    # Validation
    if args.interval < 15:
        logger.error("Interval must be at least 15 seconds")
        sys.exit(1)

    # Validate Raspberry Pi parameters
    if args.raspberry_id >= args.n_raspberry:
        logger.error(
            f"Invalid Raspberry Pi configuration: raspberry_id ({args.raspberry_id}) "
            f"must be less than n_raspberry ({args.n_raspberry})"
        )
        sys.exit(1)
    
    # Parse Scrapy settings
    scrapy_settings = {}
    if args.scrapy_settings:
        for setting in args.scrapy_settings:
            if "=" in setting:
                key, value = setting.split("=", 1)
                scrapy_settings[key] = value


    # Lance le scraper continu
    scraper = ContinuousScraper(
        interval_seconds=args.interval,
        n_raspberry=args.n_raspberry,
        raspberry_id=args.raspberry_id,
        scrapy_settings=scrapy_settings
    )
    scraper.run()


if __name__ == "__main__":
    main()
