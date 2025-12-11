import os
import sys
# Ensure project root is on sys.path so tests can import scrappy_pyronear
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scrappy_pyronear.items import PyronearItem

def test_item_fields():
    '''
    Checks that PyronearItem is correctly instantiated and behave as a Scrapy dict.
    '''
    item = PyronearItem(
        id="CAM01",
        name="Test",
        azimuth=100,
        last_moved=123456,
        image_url="http://x",
    )

    assert item["id"] == "CAM01"
    assert item["name"] == "Test"
    assert item["azimuth"] == 100
    assert item["image_url"].startswith("http")