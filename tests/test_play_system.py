import pytest
import asyncio
from play_system import play_audio_stream, _search_jiosaavn, _format_duration


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
async def test_jiosaavn_search():
    res = await _search_jiosaavn("tum hi ho")
    assert res is not None
    assert "stream_url" in res
    assert res["stream_url"].startswith("http")


@pytest.mark.asyncio
async def test_play_audio_stream():
    client = MockPyTgCalls()
    success, title, duration, msg = await play_audio_stream(-100123456789, "tum hi ho", client)
    assert success is True
    assert title != ""
    assert client.played is True
