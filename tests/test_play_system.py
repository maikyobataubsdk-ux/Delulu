import pytest
import asyncio
from play_system import play_audio_stream, fast_search_youtube, fast_extract_from_api, _format_duration


class MockPyTgCalls:
    def __init__(self):
        self.played = False

    async def play(self, chat_id, stream):
        self.played = True


def test_format_duration():
    assert _format_duration(0) == "0:00"
    assert _format_duration(65) == "1:05"
    assert _format_duration(3665) == "1:01:05"


@pytest.mark.asyncio
async def test_fast_search_youtube():
    # Direct YouTube URL should be returned immediately
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    res_url = await fast_search_youtube(yt_url)
    assert res_url == yt_url

    # Query search should return a valid YouTube URL
    res_search = await fast_search_youtube("Never Gonna Give You Up")
    assert res_search is not None
    assert "youtube.com" in res_search or "youtu.be" in res_search


@pytest.mark.asyncio
async def test_fast_extract_from_api():
    # Calling endpoint without a running FastAPI server should return None gracefully without raising
    res = await fast_extract_from_api("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert res is None or isinstance(res, dict)


@pytest.mark.asyncio
async def test_play_audio_stream():
    client = MockPyTgCalls()
    success, title, duration, msg = await play_audio_stream(-100123456789, "tum hi ho", client)
    assert success is True
    assert title != ""
    assert client.played is True
