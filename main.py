import asyncio
import os
import glob
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import yt_dlp
from SONALI_MUSIC.utils.youtube_utils import get_ytdl_base_opts

app = FastAPI(
    title="YouTube Stream Extraction API",
    description="High-performance async FastAPI server using a Cookie Pool & In-Memory TTL Cache for yt-dlp stream extraction.",
    version="1.0.0"
)

# ---------------------------------------------------------------------------
# 1. In-Memory Cache Implementation (2 Hours TTL)
# ---------------------------------------------------------------------------
CACHE_TTL = 7200  # 2 hours in seconds
stream_cache: Dict[str, Dict[str, Any]] = {}

def get_cached_stream(key: str) -> Optional[Dict[str, Any]]:
    if key in stream_cache:
        item = stream_cache[key]
        if time.time() - item["timestamp"] < CACHE_TTL:
            return item["data"]
        else:
            del stream_cache[key]
    return None

def set_cached_stream(key: str, data: Dict[str, Any]) -> None:
    stream_cache[key] = {
        "data": data,
        "timestamp": time.time()
    }

# ---------------------------------------------------------------------------
# 2. Cookie Pool Management
# ---------------------------------------------------------------------------
COOKIE_DIR = "cookies"
_cookie_index = 0

def get_next_cookie_file() -> Optional[str]:
    global _cookie_index
    if not os.path.exists(COOKIE_DIR):
        return None
    files = sorted(glob.glob(os.path.join(COOKIE_DIR, "*.txt")))
    if not files:
        return None
    cookie_file = files[_cookie_index % len(files)]
    _cookie_index += 1
    return cookie_file

# ---------------------------------------------------------------------------
# 3. ThreadPoolExecutor & Aggressive yt-dlp Options
# ---------------------------------------------------------------------------
executor = ThreadPoolExecutor(max_workers=16)

def _extract_stream_sync(url: str, is_video: bool = False) -> Dict[str, Any]:
    cookie_file = get_next_cookie_file()
    ydl_opts = get_ytdl_base_opts(cookie_file=cookie_file, is_video=is_video)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("Failed to extract video information.")

        if 'entries' in info:
            entries = [e for e in info['entries'] if e]
            if not entries:
                raise ValueError("No search results found.")
            info = entries[0]

        stream_url = info.get('url')
        if not stream_url and 'formats' in info:
            formats = info['formats']
            if not is_video:
                audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('url')]
                if audio_formats:
                    stream_url = audio_formats[-1]['url']
            if not stream_url and formats:
                stream_url = formats[-1].get('url')

        if not stream_url:
            raise ValueError("Direct stream URL could not be retrieved.")

        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "thumbnail": info.get("thumbnail"),
            "stream_url": stream_url,
            "cookie_used": os.path.basename(cookie_file) if cookie_file else None
        }

# ---------------------------------------------------------------------------
# 4. FastAPI Endpoints
# ---------------------------------------------------------------------------
class ExtractRequest(BaseModel):
    url: str
    is_video: bool = False

@app.get("/health")
async def health_check():
    return {"status": "ok", "cached_items": len(stream_cache)}

@app.get("/api/extract")
async def extract_get(
    url: str = Query(..., description="YouTube video URL or Video ID"),
    video: bool = Query(False, description="Extract video stream if True, audio if False")
):
    cache_key = f"{'video' if video else 'audio'}:{url}"
    cached_data = get_cached_stream(cache_key)
    if cached_data:
        return {"success": True, "cached": True, "data": cached_data}

    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(executor, _extract_stream_sync, url, video)
        set_cached_stream(cache_key, data)
        return {"success": True, "cached": False, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract")
async def extract_post(req: ExtractRequest):
    cache_key = f"{'video' if req.is_video else 'audio'}:{req.url}"
    cached_data = get_cached_stream(cache_key)
    if cached_data:
        return {"success": True, "cached": True, "data": cached_data}

    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(executor, _extract_stream_sync, req.url, req.is_video)
        set_cached_stream(cache_key, data)
        return {"success": True, "cached": False, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Telegram Bot Connection Pooling Guide (aiohttp.ClientSession)
# ==============================================================================
BOT_CLIENT_SESSION_GUIDE = """
# Place this helper inside your Telegram Music Bot codebase (e.g., utils/api_client.py)
import aiohttp
from typing import Optional, Dict, Any

class ExtractorAPIClient:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # High-performance TCP connector with connection pooling & DNS caching
            connector = aiohttp.TCPConnector(
                limit=100,           # Max 100 simultaneous connections
                limit_per_host=30,   # Max 30 connections to this API server
                ttl_dns_cache=300,   # DNS caching for 5 minutes
                enable_cleanup_closed=True
            )
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def get_stream_url(self, youtube_url: str, is_video: bool = False) -> Dict[str, Any]:
        session = await self.get_session()
        params = {"url": youtube_url, "video": is_video}
        async with session.get(f"{self.api_base_url}/api/extract", params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
"""
