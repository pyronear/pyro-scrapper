"""Unit tests for spiders and pipelines."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from scrapy.http import HtmlResponse
from scrapy.selector import Selector

from scrappy_pyronear.items import PyronearItem
from scrappy_pyronear.pipelines import FilteredIdsPipeline, GetImagesPipeline
from scrappy_pyronear.spiders.spider_filtered_ids import FilteredIdsSpider
from scrappy_pyronear.spiders.spider_get_image import GetImageSpider


class TestFilteredIdsPipeline:
    """Tests for the FilteredIdsPipeline."""

    def test_pipeline_filters_offline_cameras(self):
        """Test that offline cameras are filtered out."""
        pipeline = FilteredIdsPipeline()
        spider = Mock()
        spider.logger = Mock()
        pipeline.open_spider(spider)
        
        item = PyronearItem(
            id=1,
            name="Camera 1",
            offline=1,
            provider="DOT"
        )
        
        from scrapy.exceptions import DropItem
        with pytest.raises(DropItem):
            pipeline.process_item(item, spider)

    def test_pipeline_filters_non_dot_provider(self):
        """Test that non-DOT providers are filtered out."""
        pipeline = FilteredIdsPipeline()
        spider = Mock()
        spider.logger = Mock()
        pipeline.open_spider(spider)
        
        item = PyronearItem(
            id=1,
            name="Camera 1",
            offline=0,
            provider="OTHER",
            image_url="https://example.com/image.jpg"
        )
        
        from scrapy.exceptions import DropItem
        with pytest.raises(DropItem):
            pipeline.process_item(item, spider)

    def test_pipeline_filters_non_thermal_cameras(self):
        """Test that non-thermal cameras are filtered out."""
        pipeline = FilteredIdsPipeline()
        spider = Mock()
        spider.logger = Mock()
        pipeline.open_spider(spider)
        
        item = PyronearItem(
            id=1,
            name="Regular Camera",
            offline=0,
            provider="DOT",
            camera_type="visible",
            image_url="https://example.com/image.jpg"
        )
        
        from scrapy.exceptions import DropItem
        with patch.object(pipeline, '_get_image_metadata', return_value=1000):
            with pytest.raises(DropItem):
                pipeline.process_item(item, spider)

    @patch('scrappy_pyronear.pipelines.requests.head')
    def test_get_image_metadata_success(self, mock_head):
        """Test successful image metadata retrieval."""
        mock_response = Mock()
        mock_response.headers = {"Content-Length": "12345"}
        mock_head.return_value = mock_response
        
        size = FilteredIdsPipeline._get_image_metadata("https://example.com/image.jpg")
        assert size == 12345

    def test_pipeline_accepts_valid_thermal_camera(self):
        """Test that valid thermal cameras are accepted."""
        pipeline = FilteredIdsPipeline()
        spider = Mock()
        spider.logger = Mock()
        pipeline.open_spider(spider)
        
        item = PyronearItem(
            id=1,
            name="Thermal Camera",
            offline=0,
            provider="DOT",
            camera_type="thermal",
            image_url="https://example.com/image.jpg"
        )
        
        with patch.object(pipeline, '_get_image_metadata', return_value=5000):
            result = pipeline.process_item(item, spider)
            assert result["id"] == 1
            assert len(pipeline.good_ids["camera_ids"]) == 1

    def test_pipeline_saves_to_json_on_close(self):
        """Test that pipeline saves data to JSON on spider close."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = FilteredIdsPipeline()
            pipeline.output_file = Path(tmpdir) / "test_ids.json"
            
            spider = Mock()
            spider.logger = Mock()
            pipeline.open_spider(spider)
            
            # Add some test data
            pipeline.good_ids["camera_ids"].append({
                "id": 1,
                "name": "Test Camera"
            })
            
            pipeline.close_spider(spider)
            
            # Verify file was created and contains correct data
            assert pipeline.output_file.exists()
            with open(pipeline.output_file, "r") as f:
                data = json.load(f)
                assert len(data["camera_ids"]) == 1
                assert data["camera_ids"][0]["id"] == 1


class TestGetImagesPipeline:
    """Tests for the GetImagesPipeline."""

    def test_pipeline_creates_directory_structure(self):
        """Test that pipeline creates proper directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = GetImagesPipeline()
            spider = Mock()
            spider.logger = Mock()
            
            # Mock Path to use temp directory
            with patch('scrappy_pyronear.pipelines.Path') as mock_path:
                mock_path.return_value = Path(tmpdir)
                mock_path.side_effect = lambda x: Path(tmpdir) if isinstance(x, str) else Path(x)
                
                pipeline.open_spider(spider)
                # Verify directory was created
                assert spider.logger.info.called

    def test_pipeline_saves_image_to_disk(self):
        """Test that pipeline saves images to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline = GetImagesPipeline()
            pipeline.images_dir = Path(tmpdir)
            
            spider = Mock()
            spider.logger = Mock()
            
            item = PyronearItem(
                id=1,
                name="Test Camera",
                image_data=b"test image content",
                image_filename="screenshot.jpg"
            )
            
            result = pipeline.process_item(item, spider)
            
            # Verify file was created
            expected_path = Path(tmpdir) / "1_screenshot.jpg"
            assert expected_path.exists()
            assert expected_path.read_bytes() == b"test image content"

    def test_pipeline_fails_with_missing_image_data(self):
        """Test that pipeline fails when image data is missing."""
        pipeline = GetImagesPipeline()
        pipeline.images_dir = Path("/tmp")
        
        spider = Mock()
        
        item = PyronearItem(
            id=1,
            name="Test Camera",
            image_filename="screenshot.jpg"
        )
        
        from scrapy.exceptions import DropItem
        with pytest.raises(DropItem):
            pipeline.process_item(item, spider)


class TestFilteredIdsSpider:
    """Tests for the FilteredIdsSpider."""

    def test_spider_name(self):
        """Test that spider has correct name."""
        spider = FilteredIdsSpider()
        assert spider.name == "spider_filtered_ids"

    def test_spider_custom_settings(self):
        """Test that spider has correct custom settings."""
        spider = FilteredIdsSpider()
        assert 'ITEM_PIPELINES' in spider.custom_settings
        assert 'scrappy_pyronear.pipelines.FilteredIdsPipeline' in spider.custom_settings['ITEM_PIPELINES']


class TestGetImageSpider:
    """Tests for the GetImageSpider."""

    def test_spider_name(self):
        """Test that spider has correct name."""
        spider = GetImageSpider()
        assert spider.name == "spider_get_image"

    def test_spider_custom_settings(self):
        """Test that spider has correct custom settings."""
        spider = GetImageSpider()
        assert 'ITEM_PIPELINES' in spider.custom_settings
        assert 'scrappy_pyronear.pipelines.GetImagesPipeline' in spider.custom_settings['ITEM_PIPELINES']

    def test_spider_loads_good_ids_from_file(self):
        """Test that spider loads camera IDs from good_ids.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            good_ids_path = Path(tmpdir) / "good_ids.json"
            good_ids_data = {
                "camera_ids": [
                    {"id": 1, "name": "Camera 1", "image_url": "https://example.com/img1.jpg"},
                    {"id": 2, "name": "Camera 2", "image_url": "https://example.com/img2.jpg"}
                ]
            }
            
            with open(good_ids_path, "w") as f:
                json.dump(good_ids_data, f)
            
            spider = GetImageSpider()
            spider.good_ids_path = good_ids_path
            
            requests = list(spider.start_requests())
            assert len(requests) == 2
            assert requests[0].url == "https://example.com/img1.jpg"
            assert requests[1].url == "https://example.com/img2.jpg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
