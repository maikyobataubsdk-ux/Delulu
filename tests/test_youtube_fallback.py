import os
import pytest
import asyncio
import config
from SONALI_MUSIC.platforms.Youtube import is_valid_media_file, extract_video_id, YouTubeExtractor
from SONALI_MUSIC.platforms.Jiosaavn import JioSaavn, clean_song_title, SAAVN_API_ENDPOINTS


def test_clean_song_title():
    raw_title = "Ishq Official Lyrical I Amir Ameer | Faheem Abdullah | Rauhan Malik I Love Song 2024"
    cleaned = clean_song_title(raw_title)
    assert cleaned == "Ishq Amir Ameer Faheem Abdullah Rauhan Malik"
    assert clean_song_title("Shape of You (Official Music Video) [HD]") == "Shape of You"


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


def test_saavn_api_endpoints():
    assert "https://jiosaavn-a.kvinit6421.workers.dev/api/search/songs" in SAAVN_API_ENDPOINTS
    assert SAAVN_API_ENDPOINTS[0] in [
        getattr(config, "SAAVN_API_URL", None),
        getattr(config, "JIOSAAVN_API_URL", None),
        "https://jiosaavn-a.kvinit6421.workers.dev/api/search/songs",
    ]


@pytest.mark.asyncio
async def test_jiosaavn_search():
    res = await JioSaavn.search_song("Tum Hi Ho")
    # If network is available, JioSaavn returns song details
    if res:
        assert "title" in res
        assert "stream_url" in res
        assert "duration_min" in res
        assert res["stream_url"].startswith("http")


@pytest.mark.asyncio
async def test_youtube_jiosaavn_pipeline():
    from SONALI_MUSIC import YouTube
    from SONALI_MUSIC.platforms.Youtube import _JIOSAAVN_CACHE

    track_details, track_id = await YouTube.track("Tum Hi Ho")
    assert track_details is not None
    assert "title" in track_details
    assert track_id is not None

    if track_id in _JIOSAAVN_CACHE:
        assert _JIOSAAVN_CACHE[track_id].startswith("http")
        dl_res = await YouTube.download(track_id, None)
        assert dl_res is not None
        stream_url, direct = dl_res
        assert direct is True
        assert stream_url.startswith("http")
