"""Example usage and testing script for the Pyronear spiders."""

import json
import subprocess
from pathlib import Path


def run_spider_filtered_ids():
    """Run the spider_filtered_ids spider to collect and filter camera IDs."""
    print("🚀 Starting spider_filtered_ids...")
    print("-" * 60)

    result = subprocess.run(["scrapy", "crawl", "spider_filtered_ids"], cwd=Path(__file__).parent, capture_output=False)

    if result.returncode == 0:
        print("\n✅ spider_filtered_ids completed successfully")
        # Check if good_ids.json was created
        good_ids_path = Path(__file__).parent / "good_ids.json"
        if good_ids_path.exists():
            with open(good_ids_path, "r") as f:
                data = json.load(f)
                print(f"\n📊 Found {len(data['camera_ids'])} valid cameras")
                print(f"📁 Saved to: {good_ids_path}")
    else:
        print("\n❌ spider_filtered_ids failed")
        return False

    return True


def run_spider_get_image():
    """Run the spider_get_image spider to download images for valid cameras."""
    print("\n🚀 Starting spider_get_image...")
    print("-" * 60)

    result = subprocess.run(["scrapy", "crawl", "spider_get_image"], cwd=Path(__file__).parent, capture_output=False)

    if result.returncode == 0:
        print("\n✅ spider_get_image completed successfully")
    else:
        print("\n❌ spider_get_image failed")
        return False

    return True


def main():
    """Run both spiders in sequence."""
    print("=" * 60)
    print("Pyronear Scraper - Complete Workflow")
    print("=" * 60)

    # Step 1: Filter cameras
    if not run_spider_filtered_ids():
        print("\nAborting workflow - filtering step failed")
        return

    # Step 2: Download images
    if not run_spider_get_image():
        print("\nDownload step failed, but filtering was successful")
        print("You can retry the download step manually")
        return

    print("\n" + "=" * 60)
    print("✅ Complete workflow finished successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
