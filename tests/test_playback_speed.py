import os
import pytest
import config
from SONALI_MUSIC.core.call import Call
from SONALI_MUSIC.utils.formatters import speed_converter


@pytest.mark.asyncio
async def test_playback_speed_build_stream():
    call_client = Call()

    # Case 1: Default PLAYBACK_SPEED (1.15) applied when no ffmpeg params provided
    stream = call_client._build_stream("test_audio.mp3", video=False)
    assert stream._ffmpeg_parameters is not None
    assert "atempo=1.15" in stream._ffmpeg_parameters

    # Case 2: Existing ffmpeg params without speed filter gets speed filter appended
    stream_existing = call_client._build_stream("test_audio.mp3", video=False, ffmpeg="-ss 0 -to 60")
    assert "-ss 0 -to 60" in stream_existing._ffmpeg_parameters
    assert "atempo=1.15" in stream_existing._ffmpeg_parameters

    # Case 3: Explicit speed filter already in ffmpeg params is preserved without duplicate
    stream_custom = call_client._build_stream("test_audio.mp3", video=False, ffmpeg="-ss 0 -to 60 -filter:a atempo=1.5")
    assert stream_custom._ffmpeg_parameters.count("atempo=") == 1
    assert "atempo=1.5" in stream_custom._ffmpeg_parameters


def test_speed_converter_1_15():
    # 115 seconds at 1.15x speed becomes 100 seconds
    convert_str, seconds = speed_converter(115, 1.15)
    assert seconds == 100
    assert convert_str == "01:40"
