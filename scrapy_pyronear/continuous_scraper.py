"""
Script de scraping continu pour AlertWest.

Ce script lance la spider alertwest de manière continue avec un intervalle
configurable entre chaque exécution.

Usage:
    python continuous_scraper.py [--interval SECONDS]

Options:
    --interval SECONDS  Intervalle en secondes entre chaque scraping (défaut: 30)

Exemple:
    python continuous_scraper.py --interval 60  # Lance le scraping toutes les 60 secondes
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

    def __init__(self, interval_seconds=30):
        """
        Initialise le scraper continu.

        Args:
            interval_seconds (int): Intervalle en secondes entre chaque scraping
        """
        self.interval_seconds = interval_seconds
        self.running = True
        self.scrape_count = 0

        # Gestion des signaux pour arrêt propre
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handles stop signals (Ctrl+C, etc.)."""
        logger.info("Stop signal received. Stopping after the current cycle...")
        self.running = False

    def run_spider_once(self):
        """
        Lance la spider une seule fois via subprocess.

        Returns:
            bool: True si le scraping s'est bien déroulé, False sinon
        """
        try:
            logger.info(f"🚀 Start of scraping cycle #{self.scrape_count + 1}")
            start_time = time.time()

            # Lance scrapy crawl en subprocess
            result = subprocess.run(
                ["scrapy", "crawl", "alertwest"],
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
        logger.info("Press Ctrl+C to stop gracefully")

        while self.running:
            cycle_start = time.time()

            # Lance un cycle de scraping
            success = self.run_spider_once()

            if not self.running:
                break

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
  python continuous_scraper.py                    # Default interval (60s)
  python continuous_scraper.py --interval 90      # Every 90 seconds
  python continuous_scraper.py --interval 300     # Every 5 minutes
        """,
    )

    parser.add_argument(
        "--interval", type=int, default=60, help="Interval in seconds between each scraping (default: 60)"
    )

    args = parser.parse_args()

    # Validation
    if args.interval < 15:
        logger.error("Interval must be at least 15 seconds")
        sys.exit(1)

    # Lance le scraper continu
    scraper = ContinuousScraper(interval_seconds=args.interval)
    scraper.run()


if __name__ == "__main__":
    main()
