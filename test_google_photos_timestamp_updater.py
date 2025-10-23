#!/usr/bin/env python3
"""
Unit tests for Google Photos Timestamp Updater

Tests cover core functionality including path validation, metadata parsing,
timestamp conversion, and file operations.
"""

import unittest
import tempfile
import os
import json
import shutil
from unittest.mock import patch, mock_open
from datetime import datetime

# Import the functions we want to test
from google_photos_timestamp_updater import (
    validate_path,
    test_read_access,
    test_write_access,
    parse_metadata_file,
    convert_timestamp_for_file_operations,
    get_corresponding_media_file,
    verify_media_file_exists,
    update_file_timestamps,
    detect_orphaned_media_files
)


class TestPathValidation(unittest.TestCase):
    """Test cases for path validation functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_validate_path_valid_directory(self):
        """Test validate_path with a valid directory."""
        self.assertTrue(validate_path(self.temp_dir))
    
    def test_validate_path_nonexistent_path(self):
        """Test validate_path with non-existent path."""
        nonexistent_path = os.path.join(self.temp_dir, "nonexistent")
        self.assertFalse(validate_path(nonexistent_path))
    
    def test_validate_path_file_not_directory(self):
        """Test validate_path with a file instead of directory."""
        self.assertFalse(validate_path(self.temp_file.name))
    
    def test_read_access_valid_directory(self):
        """Test test_read_access with accessible directory."""
        self.assertTrue(test_read_access(self.temp_dir))
    
    def test_write_access_valid_directory(self):
        """Test test_write_access with writable directory."""
        self.assertTrue(test_write_access(self.temp_dir))


class TestMetadataParsing(unittest.TestCase):
    """Test cases for metadata parsing functions."""
    
    def setUp(self):
        """Set up test fixtures with sample metadata."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Valid metadata structure
        self.valid_metadata = {
            "title": "test_photo.jpg",
            "description": "",
            "imageViews": "0",
            "creationTime": {
                "timestamp": "1571673729",
                "formatted": "Oct 21, 2019, 7:08:49 PM UTC"
            },
            "photoTakenTime": {
                "timestamp": "1571673729",
                "formatted": "Oct 21, 2019, 7:08:49 PM UTC"
            },
            "geoData": {
                "latitude": 0.0,
                "longitude": 0.0,
                "altitude": 0.0,
                "latitudeSpan": 0.0,
                "longitudeSpan": 0.0
            }
        }
        
        # Create valid metadata file
        self.valid_metadata_file = os.path.join(self.temp_dir, "test.jpg.supplemental-metadata.json")
        with open(self.valid_metadata_file, 'w') as f:
            json.dump(self.valid_metadata, f)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_parse_metadata_file_valid(self):
        """Test parsing valid metadata file."""
        timestamp = parse_metadata_file(self.valid_metadata_file)
        self.assertEqual(timestamp, 1571673729)
    
    def test_parse_metadata_file_missing_photo_taken_time(self):
        """Test parsing metadata file missing photoTakenTime."""
        invalid_metadata = {"title": "test.jpg"}
        invalid_file = os.path.join(self.temp_dir, "invalid.json")
        with open(invalid_file, 'w') as f:
            json.dump(invalid_metadata, f)
        
        timestamp = parse_metadata_file(invalid_file)
        self.assertIsNone(timestamp)
    
    def test_parse_metadata_file_invalid_json(self):
        """Test parsing file with invalid JSON."""
        invalid_file = os.path.join(self.temp_dir, "invalid.json")
        with open(invalid_file, 'w') as f:
            f.write("invalid json content")
        
        timestamp = parse_metadata_file(invalid_file)
        self.assertIsNone(timestamp)
    
    def test_parse_metadata_file_nonexistent(self):
        """Test parsing non-existent metadata file."""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.json")
        timestamp = parse_metadata_file(nonexistent_file)
        self.assertIsNone(timestamp)


class TestTimestampConversion(unittest.TestCase):
    """Test cases for timestamp conversion functions."""
    
    def test_convert_timestamp_valid(self):
        """Test converting valid timestamp."""
        valid_timestamp = 1571673729  # Oct 21, 2019
        result = convert_timestamp_for_file_operations(valid_timestamp)
        self.assertEqual(result, valid_timestamp)
    
    def test_convert_timestamp_negative(self):
        """Test converting negative timestamp."""
        with self.assertRaises(ValueError):
            convert_timestamp_for_file_operations(-1)
    
    def test_convert_timestamp_zero(self):
        """Test converting zero timestamp."""
        with self.assertRaises(ValueError):
            convert_timestamp_for_file_operations(0)
    
    def test_convert_timestamp_too_old(self):
        """Test converting timestamp that's too old."""
        old_timestamp = 100000000  # 1973, before reasonable minimum
        with self.assertRaises(ValueError):
            convert_timestamp_for_file_operations(old_timestamp)
    
    def test_convert_timestamp_too_future(self):
        """Test converting timestamp that's too far in future."""
        future_timestamp = int(datetime.now().timestamp()) + (2 * 365 * 24 * 60 * 60)  # 2 years from now
        with self.assertRaises(ValueError):
            convert_timestamp_for_file_operations(future_timestamp)


class TestMediaFileOperations(unittest.TestCase):
    """Test cases for media file operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test media file
        self.media_file = os.path.join(self.temp_dir, "test_photo.jpg")
        with open(self.media_file, 'w') as f:
            f.write("fake image content")
        
        # Create corresponding metadata file path
        self.metadata_file = self.media_file + ".supplemental-metadata.json"
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_corresponding_media_file_valid(self):
        """Test getting corresponding media file path."""
        media_path = get_corresponding_media_file(self.metadata_file)
        self.assertEqual(media_path, self.media_file)
    
    def test_get_corresponding_media_file_invalid_suffix(self):
        """Test getting media file path with invalid suffix."""
        invalid_metadata_path = os.path.join(self.temp_dir, "test.json")
        with self.assertRaises(ValueError):
            get_corresponding_media_file(invalid_metadata_path)
    
    def test_verify_media_file_exists_valid(self):
        """Test verifying existing media file."""
        self.assertTrue(verify_media_file_exists(self.media_file))
    
    def test_verify_media_file_exists_nonexistent(self):
        """Test verifying non-existent media file."""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.jpg")
        self.assertFalse(verify_media_file_exists(nonexistent_file))
    
    def test_update_file_timestamps_valid(self):
        """Test updating file timestamps with valid timestamp."""
        valid_timestamp = 1571673729  # Oct 21, 2019
        result = update_file_timestamps(self.media_file, valid_timestamp)
        self.assertTrue(result)
        
        # Verify timestamp was actually updated
        stat_result = os.stat(self.media_file)
        self.assertEqual(int(stat_result.st_mtime), valid_timestamp)
    
    def test_update_file_timestamps_invalid_timestamp(self):
        """Test updating file timestamps with invalid timestamp."""
        invalid_timestamp = -1
        result = update_file_timestamps(self.media_file, invalid_timestamp)
        self.assertFalse(result)
    
    def test_update_file_timestamps_nonexistent_file(self):
        """Test updating timestamps for non-existent file."""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.jpg")
        valid_timestamp = 1571673729
        result = update_file_timestamps(nonexistent_file, valid_timestamp)
        self.assertFalse(result)


class TestOrphanedMediaDetection(unittest.TestCase):
    """Test cases for orphaned media file detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create media files
        self.media_with_metadata = os.path.join(self.temp_dir, "photo1.jpg")
        self.media_without_metadata = os.path.join(self.temp_dir, "photo2.jpg")
        
        with open(self.media_with_metadata, 'w') as f:
            f.write("fake content")
        with open(self.media_without_metadata, 'w') as f:
            f.write("fake content")
        
        # Create metadata file for only one media file
        self.metadata_file = self.media_with_metadata + ".supplemental-metadata.json"
        with open(self.metadata_file, 'w') as f:
            f.write('{"photoTakenTime": {"timestamp": "1571673729"}}')
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_detect_orphaned_media_files(self):
        """Test detection of orphaned media files."""
        metadata_files = [self.metadata_file]
        media_files = [self.media_with_metadata, self.media_without_metadata]
        
        orphaned = detect_orphaned_media_files(metadata_files, media_files)
        
        self.assertEqual(len(orphaned), 1)
        self.assertIn(self.media_without_metadata, orphaned)
        self.assertNotIn(self.media_with_metadata, orphaned)
    
    def test_detect_orphaned_media_files_no_orphans(self):
        """Test detection when no orphaned files exist."""
        metadata_files = [self.metadata_file]
        media_files = [self.media_with_metadata]  # Only media file with metadata
        
        orphaned = detect_orphaned_media_files(metadata_files, media_files)
        
        self.assertEqual(len(orphaned), 0)


if __name__ == '__main__':
    unittest.main()