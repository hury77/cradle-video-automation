import os
import sys
import zipfile
import tempfile
import pytest
from pathlib import Path

# Add desktop-app/src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "desktop-app" / "src"))

from zip_utils import unzip_and_cleanup

def test_macos_metadata_is_ignored():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = tmp_path / "test_archive.zip"
        
        # Create a mock video file content (e.g., 1000 bytes)
        mock_video_content = b'A' * 1000
        # Create mock AppleDouble metadata content (e.g., 600 bytes)
        mock_metadata_content = b'M' * 600
        # Create mock DS_Store content (e.g., 200 bytes)
        mock_ds_store_content = b'D' * 200
        
        # Build the ZIP file
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # Add files to the zip in a specific order so metadata is processed last
            zipf.writestr("video.mp4", mock_video_content)
            zipf.writestr("__MACOSX/._video.mp4", mock_metadata_content)
            zipf.writestr(".DS_Store", mock_ds_store_content)
        
        # Act
        result = unzip_and_cleanup(str(zip_path))
        
        # Assert
        assert result['was_zip'] is True
        assert result['success'] is True
        
        # Find the extracted file
        # The expected output name according to zip_utils logic: 
        # file_path.stem + original_suffix -> test_archive.mp4
        expected_out_file = tmp_path / "test_archive.mp4"
        
        assert expected_out_file.exists(), "The extracted video file should exist"
        assert expected_out_file.stat().st_size == 1000, "The extracted file should be exactly 1000 bytes (not overwritten by 600-byte metadata)"
        
        # Ensure only 1 file was extracted (metadata ignored)
        assert len(result['extracted_files']) == 1
        
        # No .DS_Store was created
        ds_store = tmp_path / "test_archive"  # Since suffix is empty, it would be 'test_archive'
        assert not ds_store.exists(), ".DS_Store should have been skipped"
