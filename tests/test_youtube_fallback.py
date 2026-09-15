import os
import pytest
import asyncio
from SONALI_MUSIC.platforms.Youtube import is_valid_media_file, extract_video_id, YouTubeExtractor
from SONALI_MUSIC.platforms.Jiosaavn import JioSaavn


def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_is_valid_media_file(tmp_path):
    # Test non-existent file
    assert not is_valid_media_file(str(tmp_path / "non_existent.mp3"))

    # Test small / invalid file
    small_file = tmp_path / "small.mp3"
    small_file.write_bytes(b"hello")
    assert not is_valid_media_file(str(small_file))

    # Test dummy error JSON file
    error_json = tmp_path / "error.mp3"
    error_json.write_bytes(b'{"error": "bot check required"}' + b"0" * 2000)
    assert not is_valid_media_file(str(error_json))

    # Test valid media binary file
    valid_file = tmp_path / "valid.mp3"
    valid_file.write_bytes(b"\xFF\xFB\x90\x44" + b"\x00" * 5000)
    assert is_valid_media_file(str(valid_file))


@pytest.mark.asyncio
async def test_jiosaavn_search():
    res = await JioSaavn.search_song("Tum Hi Ho")
    # If network is available, JioSaavn returns song details
    if res:
        assert "title" in res
        assert "stream_url" in res
        assert "duration_min" in res
