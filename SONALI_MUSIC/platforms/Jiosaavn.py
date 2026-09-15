import os
import aiohttp
from typing import Optional, Tuple, Dict, Any
from SONALI_MUSIC import LOGGER

DOWNLOAD_DIR = os.path.abspath("downloads")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

SAAVN_API_ENDPOINTS = [
    "https://saavn.dev/api/search/songs",
    "https://jiosaavn-api-private-us.vercel.app/search/songs",
    "https://saavn.me/search/songs",
]


class JioSaavnAPI:
    """Helper API class for JioSaavn audio search and direct stream downloading."""

    @staticmethod
    async def search_song(query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        LOGGER(__name__).info(f"[JIOSAAVN] Searching JioSaavn for query: {query}")
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            for endpoint in SAAVN_API_ENDPOINTS:
                try:
                    params = {"query": query, "limit": 1}
                    async with session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("data", {}).get("results", []) if isinstance(data.get("data"), dict) else data.get("data", [])
                            if not results and isinstance(data, list):
                                results = data
                            if results and len(results) > 0:
                                song = results[0]
                                title = song.get("name") or song.get("title") or query
                                song_id = song.get("id", "saavn_track")
                                duration = song.get("duration") or 0
                                try:
                                    duration_sec = int(duration)
                                except Exception:
                                    duration_sec = 0
                                duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "3:30"

                                # Thumbnails
                                image_list = song.get("image") or song.get("downloadUrl") or []
                                thumb = "https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg"
                                if isinstance(image_list, list) and image_list:
                                    thumb = image_list[-1].get("url") or image_list[-1].get("link") or thumb
                                elif isinstance(image_list, str):
                                    thumb = image_list

                                # Download URLs
                                download_urls = song.get("downloadUrl") or []
                                stream_url = None
                                if isinstance(download_urls, list) and download_urls:
                                    # Pick highest quality link available
                                    stream_url = download_urls[-1].get("url") or download_urls[-1].get("link")
                                elif isinstance(download_urls, str):
                                    stream_url = download_urls

                                if stream_url:
                                    LOGGER(__name__).info(f"[JIOSAAVN] Found track on JioSaavn: {title} ({song_id})")
                                    return {
                                        "title": title,
                                        "id": song_id,
                                        "duration_min": duration_min,
                                        "thumb": thumb,
                                        "stream_url": stream_url,
                                    }
                except Exception as e:
                    LOGGER(__name__).debug(f"[JIOSAAVN] Search endpoint {endpoint} failed: {e}")

        return None

    @classmethod
    async def download_song_by_query(cls, query: str, dest_filename: str) -> Optional[str]:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        dest_path = os.path.join(DOWNLOAD_DIR, dest_filename)

        song_info = await cls.search_song(query)
        if not song_info or not song_info.get("stream_url"):
            return None

        stream_url = song_info["stream_url"]
        try:
            LOGGER(__name__).info(f"[JIOSAAVN] Downloading track audio from JioSaavn stream: {stream_url}")
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
                            LOGGER(__name__).info(f"[JIOSAAVN] Download successful: {dest_path}")
                            return dest_path
        except Exception as e:
            LOGGER(__name__).error(f"[JIOSAAVN] Failed to download JioSaavn audio: {e}")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception:
                    pass

        return None


JioSaavn = JioSaavnAPI()
