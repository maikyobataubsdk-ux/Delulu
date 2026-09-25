import asyncio
import re
from typing import Tuple, Dict, Any, Optional
import aiohttp
import yt_dlp
from pytgcalls.types import MediaStream, AudioQuality


class SilentLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


# Client Spoofing Profiles (Sequential Fallback)
CLIENT_PROFILES = [
    ["ios", "tvhtml5"],
    ["android", "mweb"],
    ["web"],
]

JIOSAAVN_ENDPOINTS = [
    "https://jiosaavn-a.kvinit6421.workers.dev/api/search/songs",
    "https://saavn.dev/api/search/songs",
    "https://jiosaavn-api-private-us.vercel.app/search/songs",
]


def _format_duration(seconds: int) -> str:
    if not seconds:
        return "0:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


async def _check_stream_url(url: str) -> bool:
    """Verifies that the extracted HTTP audio stream URL is playable and returns 200/206 status without 403 Forbidden."""
    if not url or not url.startswith("http"):
        return False
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as resp:
                if resp.status in (200, 206):
                    return True
                if resp.status == 403:
                    return False
            async with session.get(url, headers={"Range": "bytes=0-1024"}, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as resp:
                return resp.status in (200, 206)
    except Exception:
        return True


def _extract_yt_info(url_or_query: str, client_clients: list) -> Optional[Dict[str, Any]]:
    """Synchronous yt-dlp extraction with specified player_client profile."""
    ydl_opts = {
        "format": "bestaudio/best/ba/b",
        "format_sort": ["res", "ext:m4a:m4a", "acodec"],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "logger": SilentLogger(),
        "extractor_args": {
            "youtube": {
                "player_client": client_clients,
            }
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url_or_query, download=False)
            if not info:
                return None
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            stream_url = info.get("url")

            # Safe format extractor fallback (manual format parsing)
            if not stream_url and "formats" in info and isinstance(info["formats"], list):
                formats = info["formats"]
                # Primary: Select the first format where acodec != 'none' and vcodec == 'none'
                for fmt in formats:
                    if not isinstance(fmt, dict):
                        continue
                    acodec = fmt.get("acodec")
                    vcodec = fmt.get("vcodec")
                    if acodec and acodec != "none" and (not vcodec or vcodec == "none"):
                        if fmt.get("url"):
                            stream_url = fmt["url"]
                            break

                # Secondary: If no audio-only stream is found, pick best stream containing audio (acodec != 'none')
                if not stream_url:
                    for fmt in reversed(formats):
                        if not isinstance(fmt, dict):
                            continue
                        acodec = fmt.get("acodec")
                        if acodec and acodec != "none":
                            if fmt.get("url"):
                                stream_url = fmt["url"]
                                break

            title = info.get("title", "Unknown Track")
            duration_sec = info.get("duration", 0)
            duration_str = _format_duration(duration_sec) if isinstance(duration_sec, int) else "0:00"

            if stream_url:
                return {
                    "stream_url": stream_url,
                    "title": title,
                    "duration": duration_str,
                    "source": "YouTube",
                }
    except Exception:
        pass
    return None


def _get_flat_search_results(query: str, limit: int = 3) -> list:
    """Uses yt-dlp flat extraction to get top video URLs for search queries."""
    if re.match(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/", query):
        return [query]

    search_target = f"ytsearch{limit}:{query}"
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "logger": SilentLogger(),
    }
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_target, download=False)
            if info and "entries" in info:
                for entry in info["entries"]:
                    if not entry:
                        continue
                    url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    if url:
                        results.append(url)
    except Exception:
        pass

    if not results:
        results.append(query)
    return results


async def _search_jiosaavn(query: str) -> Optional[Dict[str, Any]]:
    """Fallback search on JioSaavn API if YouTube fails."""
    clean_q = re.sub(r"[\(\[\{].*?[\)\]\}]", "", query).strip() or query
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        for endpoint in JIOSAAVN_ENDPOINTS:
            try:
                params = {"query": clean_q, "limit": 5}
                async with session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = (
                            data.get("data", {}).get("results", [])
                            if isinstance(data.get("data"), dict)
                            else data.get("data", [])
                        )
                        if not results or not isinstance(results, list):
                            continue

                        song = results[0]
                        title = song.get("name") or song.get("title") or "JioSaavn Track"
                        duration_sec = song.get("duration") or song.get("duration_sec") or 0
                        try:
                            duration_sec = int(duration_sec)
                        except Exception:
                            duration_sec = 0
                        duration_str = _format_duration(duration_sec)

                        download_urls = (
                            song.get("downloadUrl")
                            or song.get("download_url")
                            or song.get("media_url")
                            or []
                        )
                        stream_url = None
                        if isinstance(download_urls, list) and download_urls:
                            for item in download_urls:
                                if isinstance(item, dict) and item.get("quality") in ["320kbps", "160kbps"]:
                                    stream_url = item.get("url") or item.get("link")
                                    if stream_url:
                                        break
                            if not stream_url:
                                last = download_urls[-1]
                                stream_url = last.get("url") if isinstance(last, dict) else last.get("link") if isinstance(last, dict) else last
                        elif isinstance(download_urls, str):
                            stream_url = download_urls

                        if stream_url:
                            return {
                                "stream_url": stream_url,
                                "title": title,
                                "duration": duration_str,
                                "source": "JioSaavn",
                            }
            except Exception:
                continue
    return None


async def play_audio_stream(
    chat_id: int,
    query: str,
    pytgcalls_client: Any,
) -> Tuple[bool, str, str, str]:
    """
    Modular, async function to search, extract audio stream, and play audio in VC.
    Primary Strategy: YouTube extraction with client spoofing fallback.
    Secondary Strategy: JioSaavn API fallback.

    Returns:
        (success: bool, title: str, duration: str, message: str)
    """
    loop = asyncio.get_event_loop()
    extracted_data = None

    # Step 1: Primary YouTube Search & Direct Audio Extraction with Client Spoofing
    video_targets = await loop.run_in_executor(None, _get_flat_search_results, query, 3)

    for target_url in video_targets:
        if extracted_data:
            break
        for profile in CLIENT_PROFILES:
            info = await loop.run_in_executor(None, _extract_yt_info, target_url, profile)
            if info and info.get("stream_url"):
                stream_valid = await _check_stream_url(info["stream_url"])
                if stream_valid:
                    extracted_data = info
                    break

    # Step 2: Secondary JioSaavn API Fallback
    if not extracted_data:
        jio_info = await _search_jiosaavn(query)
        if jio_info and jio_info.get("stream_url"):
            extracted_data = jio_info

    if not extracted_data or not extracted_data.get("stream_url"):
        return (
            False,
            "",
            "",
            f"Failed to extract audio stream for '{query}' from both YouTube and JioSaavn.",
        )

    # Step 3: Stream to PyTgCalls
    stream_url = extracted_data["stream_url"]
    title = extracted_data["title"]
    duration = extracted_data["duration"]
    source = extracted_data["source"]

    try:
        media_stream = MediaStream(
            media_path=stream_url,
            audio_parameters=AudioQuality.HIGH,
            ffmpeg_parameters="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        )
        await pytgcalls_client.play(chat_id, media_stream)
        msg = f"Started playing '{title}' ({duration}) via {source}."
        return (True, title, duration, msg)
    except Exception as e:
        return (
            False,
            title,
            duration,
            f"Failed to play audio stream in PyTgCalls: {str(e)}",
        )
