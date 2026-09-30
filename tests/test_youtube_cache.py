import os
import pytest
import tempfile
import asyncio
from SONALI_MUSIC.platforms.Youtube import find_downloaded_file, is_valid_media_file, YouTubeExtractor, DOWNLOAD_DIR
from SONALI_MUSIC.utils.youtube_utils import AudioCache


def test_is_valid_media_file():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"0" * 2048)
        tf_path = tf.name

    try:
        assert is_valid_media_file(tf_path) is True
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b'{"error": "Forbidden"}')
        tf_path_err = tf.name

    try:
        assert is_valid_media_file(tf_path_err) is False
    finally:
        if os.path.exists(tf_path_err):
            os.remove(tf_path_err)


def test_find_downloaded_file_strict_matching():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    target_vid = "P8PWN1OmZOA"
    similar_vid = "P8PWN1OmZOA_extra"

    file_similar = os.path.join(DOWNLOAD_DIR, f"{similar_vid}.mp3")
    with open(file_similar, "wb") as f:
        f.write(b"0" * 2048)

    file_target = os.path.join(DOWNLOAD_DIR, f"{target_vid}.mp3")

    try:
        if os.path.exists(file_target):
            os.remove(file_target)

        # Before target file exists, finding target_vid should return None (should NOT pick up similar_vid)
        found = find_downloaded_file(target_vid, is_video=False)
        assert found != file_similar
        assert found is None

        # Create actual target file
        with open(file_target, "wb") as f:
            f.write(b"1" * 2048)

        found = find_downloaded_file(target_vid, is_video=False)
        assert found == file_target
    finally:
        if os.path.exists(file_similar):
            os.remove(file_similar)
        if os.path.exists(file_target):
            os.remove(file_target)


def test_audiocache_integration():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    cache_vid = "TESTCACHE123"
    cache_file = os.path.join(DOWNLOAD_DIR, f"{cache_vid}.mp3")

    with open(cache_file, "wb") as f:
        f.write(b"C" * 2048)

    try:
        AudioCache.set(video_id=cache_vid, local_path=cache_file, source="youtube")
        retrieved = find_downloaded_file(cache_vid, is_video=False)
        assert retrieved == cache_file
    finally:
        if os.path.exists(cache_file):
            os.remove(cache_file)
