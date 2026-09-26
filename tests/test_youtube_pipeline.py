import os
import unittest
import asyncio
import time
import shutil
import tempfile
import config
from SONALI_MUSIC.utils.youtube_utils import (
    CircuitBreaker,
    AudioCache,
    classify_ytdl_error,
    get_ytdl_base_opts,
)
from SONALI_MUSIC.platforms.Youtube import is_cookie_usable as youtube_is_cookie_usable
from SONALI_MUSIC.platforms.Jiosaavn import (
    clean_song_title,
    calculate_similarity,
    JioSaavn,
)


class TestYouTubePipeline(unittest.TestCase):

    def test_format_selector(self):
        opts = get_ytdl_base_opts(is_video=False)
        self.assertEqual(opts["format"], "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best")
        self.assertEqual(opts["format_sort"], ["res", "ext:m4a:m4a", "acodec"])

    def test_manual_format_parsing(self):
        mock_info = {
            "title": "Sample Song",
            "duration": 200,
            "formats": [
                {"format_id": "140", "acodec": "mp4a.40.2", "vcodec": "none", "url": "http://example.com/audio1.m4a"},
                {"format_id": "18", "acodec": "mp4a.40.2", "vcodec": "avc1.42001E", "url": "http://example.com/video1.mp4"},
            ]
        }
        formats = mock_info["formats"]
        stream_url = None
        for fmt in formats:
            if fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") in (None, "none"):
                stream_url = fmt.get("url")
                break
        self.assertEqual(stream_url, "http://example.com/audio1.m4a")

        mock_info_video = {
            "formats": [
                {"format_id": "18", "acodec": "mp4a.40.2", "vcodec": "avc1.42001E", "url": "http://example.com/video1.mp4"},
            ]
        }
        formats_v = mock_info_video["formats"]
        stream_url_v = None
        for fmt in formats_v:
            if fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") in (None, "none"):
                stream_url_v = fmt.get("url")
                break
        if not stream_url_v:
            for fmt in reversed(formats_v):
                if fmt.get("acodec") not in (None, "none"):
                    stream_url_v = fmt.get("url")
                    break
        self.assertEqual(stream_url_v, "http://example.com/video1.mp4")

    def test_error_classification(self):
        err1, _ = classify_ytdl_error("Requested format is not available")
        self.assertEqual(err1, "FORMAT_ERROR")

        err2, _ = classify_ytdl_error("Sign in to confirm you're not a bot")
        self.assertEqual(err2, "BOT_CHECK")

        err3, _ = classify_ytdl_error("HTTP Error 403: Forbidden")
        self.assertEqual(err3, "HTTP_403")

        err4, _ = classify_ytdl_error("HTTP Error 429: Too Many Requests")
        self.assertEqual(err4, "RATE_LIMIT")

        err5, _ = classify_ytdl_error("gaierror: [Errno -2] Name or service not known")
        self.assertEqual(err5, "DNS_ERROR")

    def test_circuit_breaker(self):
        url = "http://test-dead-api.xyz/download"
        self.assertTrue(CircuitBreaker.is_available(url))

        # DNS fail -> open circuit for 30 min
        CircuitBreaker.record_failure(url, error_type="dns")
        self.assertFalse(CircuitBreaker.is_available(url))

        # Reset success
        CircuitBreaker.record_success(url)
        self.assertTrue(CircuitBreaker.is_available(url))

        # 3 failures -> open circuit
        url2 = "http://test-api-500.com/api"
        CircuitBreaker.record_failure(url2, status_code=500)
        self.assertTrue(CircuitBreaker.is_available(url2))
        CircuitBreaker.record_failure(url2, status_code=500)
        self.assertTrue(CircuitBreaker.is_available(url2))
        CircuitBreaker.record_failure(url2, status_code=500)
        self.assertFalse(CircuitBreaker.is_available(url2))

    def test_clean_song_title(self):
        raw = "Kesariya (Official Video) [Lyrics] 4K HD - Arijit Singh"
        cleaned = clean_song_title(raw)
        self.assertNotIn("Official Video", cleaned)
        self.assertNotIn("Lyrics", cleaned)
        self.assertNotIn("4K", cleaned)
        self.assertNotIn("HD", cleaned)
        self.assertEqual(cleaned, "Kesariya - Arijit Singh")

    def test_title_similarity(self):
        s1 = "Kesariya Arijit Singh"
        s2 = "Kesariya Brahmastra Arijit Singh"
        sim = calculate_similarity(clean_song_title(s1), clean_song_title(s2))
        self.assertGreater(sim, 0.7)

    def test_audio_cache(self):
        temp_dir = tempfile.mkdtemp()
        dummy_file = os.path.join(temp_dir, "test_vid.mp3")
        with open(dummy_file, "wb") as f:
            f.write(b"0" * 2000)

        vid_id = "test_vid_123"
        AudioCache.set(video_id=vid_id, local_path=dummy_file, title="Test Song", duration=180)

        cached = AudioCache.get(vid_id)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["local_path"], dummy_file)

        # Cleanup dummy file -> should invalidate cache on get
        os.remove(dummy_file)
        cached_after_delete = AudioCache.get(vid_id)
        self.assertIsNone(cached_after_delete)

        shutil.rmtree(temp_dir)

    def test_youtube_imports(self):
        self.assertIsNotNone(youtube_is_cookie_usable)

    def test_cobalt_url_config(self):
        self.assertIsNone(config.COBALT_API_URL)
        self.assertIsNone(config.SELF_HOSTED_COBALT_URL)


if __name__ == "__main__":
    unittest.main()
