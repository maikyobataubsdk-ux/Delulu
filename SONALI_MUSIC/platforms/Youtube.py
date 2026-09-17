import asyncio
import os
import re
import traceback
from typing import Union, Optional, Tuple, Dict, Any, List
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
import aiohttp

import config
from SONALI_MUSIC import LOGGER
from SONALI_MUSIC.platforms.Jiosaavn import JioSaavn, clean_song_title
from SONALI_MUSIC.utils.youtube_utils import (
    get_cookie_file,
    get_cookie_files,
    get_valid_cookie_files,
    analyze_cookies,
    classify_ytdl_error,
    get_ffmpeg_path,
    is_bgutil_server_running,
    get_ytdl_base_opts,
    mark_cookie_unusable,
    CircuitBreaker,
    AudioCache,
)

try:
    from py_yt import VideosSearch, Playlist
except ImportError:
    try:
        from youtubesearchpython.__future__ import VideosSearch, Playlist
    except ImportError:
        VideosSearch = None
        Playlist = None

API_URL = getattr(config, "API_URL", None)
VIDEO_API_URL = getattr(config, "VIDEO_API_URL", None)
SHRUTI_API_URL = getattr(config, "SHRUTI_API_URL", None)
SHRUTI_API_KEY = getattr(config, "SHRUTI_API_KEY", None)
SELF_HOSTED_COBALT_URL = getattr(config, "SELF_HOSTED_COBALT_URL", None)
YTPROXY_URL = getattr(config, "YTPROXY_URL", None)
POT_PROVIDER_URL = getattr(config, "POT_PROVIDER_URL", "http://127.0.0.1:4416")

DOWNLOAD_DIR = os.path.abspath("downloads")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}
_JIOSAAVN_CACHE: Dict[str, str] = {}


def extract_video_id(link: str) -> str:
    if not link:
        return ""
    link = link.strip()
    if "shorts/" in link:
        return link.split("shorts/")[-1].split("?")[0].split("&")[0].split("/")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0].split("&")[0].split("/")[0]
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0].split("?")[0]
    return link.split("&")[0].split("?")[0].split("/")[-1]


def time_to_seconds(time) -> int:
    stringt = str(time).strip()
    if not stringt or stringt == "None":
        return 0
    try:
        return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))
    except Exception:
        return 0


def is_valid_media_file(file_path: str, min_size: int = 1024) -> bool:
    if not os.path.exists(file_path):
        return False
    size = os.path.getsize(file_path)
    if size < min_size:
        return False
    try:
        with open(file_path, "rb") as f:
            header = f.read(512)
            if header.strip().startswith(b"{") or b'"error"' in header.lower() or b'"message"' in header.lower():
                return False
    except Exception:
        return False
    return True


def find_downloaded_file(video_id: str, is_video: bool = False) -> Optional[str]:
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        return None

    exts = [".mp4", ".mkv", ".webm"] if is_video else [".mp3", ".m4a", ".webm", ".opus", ".mp4", ".aac"]
    for ext in exts:
        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}{ext}")
        if is_valid_media_file(file_path):
            return file_path

    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(f"{video_id}."):
            file_path = os.path.join(DOWNLOAD_DIR, f)
            if is_valid_media_file(file_path):
                return file_path

    return None


async def _save_stream_to_file(session: aiohttp.ClientSession, url: str, dest_path: str, headers: Optional[dict] = None) -> bool:
    try:
        req_headers = DEFAULT_HEADERS.copy()
        if headers:
            req_headers.update(headers)
        async with session.get(url, headers=req_headers, timeout=aiohttp.ClientTimeout(total=300)) as resp:
            if resp.status == 200:
                with open(dest_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
                return is_valid_media_file(dest_path)
    except Exception as e:
        LOGGER(__name__).debug(f"Failed to save stream from {url}: {e}")
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
    return False


class YouTubeExtractor:
    """Centralized Multi-Provider External API & Local yt-dlp Extraction Pipeline."""

    @staticmethod
    async def _try_jiosaavn_api(video_id: str, is_video: bool, title: str = "", artist: str = "", duration_sec: int = 0) -> Optional[str]:
        if is_video:
            return None
        if video_id in _JIOSAAVN_CACHE:
            LOGGER(__name__).info(f"[YT-API] Found cached JioSaavn direct stream URL for {video_id}")
            return _JIOSAAVN_CACHE[video_id]

        search_query = clean_song_title(title) if title else video_id
        if not search_query or search_query == video_id:
            LOGGER(__name__).warning(f"[YT-API] JioSaavn fallback skipped for {video_id}: No clean metadata/title available")
            return None
        try:
            LOGGER(__name__).info(f"[YT-API] Attempting JioSaavn audio search for '{search_query}' ({video_id})")
            song_info = await JioSaavn.search_song(
                query=search_query,
                target_title=title,
                target_artist=artist,
                target_duration=duration_sec,
            )
            if song_info and song_info.get("stream_url"):
                stream_url = song_info["stream_url"]
                _JIOSAAVN_CACHE[video_id] = stream_url
                LOGGER(__name__).info(f"[YT-API] JioSaavn direct stream URL obtained for {video_id}: {stream_url}")
                return stream_url
        except Exception as e:
            LOGGER(__name__).warning(f"[YT-API] JioSaavn API failed for {video_id}: {e}")
        return None

    @staticmethod
    async def _try_shruti_api(video_id: str, is_video: bool) -> Optional[str]:
        if not SHRUTI_API_URL or not CircuitBreaker.is_available(SHRUTI_API_URL):
            return None
        dest_ext = ".mp4" if is_video else ".mp3"
        dest_path = os.path.join(DOWNLOAD_DIR, f"{video_id}{dest_ext}")
        media_type = "video" if is_video else "audio"
        try:
            LOGGER(__name__).info(f"[YT-API] Attempting Shruti API for {video_id} ({media_type})")
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                url = f"{SHRUTI_API_URL}/download"
                params = {"url": video_id, "type": media_type, "api_key": SHRUTI_API_KEY}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                        if is_valid_media_file(dest_path):
                            CircuitBreaker.record_success(SHRUTI_API_URL)
                            LOGGER(__name__).info(f"[YT-API] Shruti API successful for {video_id}")
                            return dest_path
                        elif os.path.exists(dest_path):
                            os.remove(dest_path)
                    else:
                        CircuitBreaker.record_failure(SHRUTI_API_URL, status_code=resp.status)
        except Exception as e:
            err_cat, _ = classify_ytdl_error(e)
            CircuitBreaker.record_failure(SHRUTI_API_URL, error_type=err_cat)
            LOGGER(__name__).warning(f"[YT-API] Shruti API failed for {video_id}: {e}")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception:
                    pass
        return None

    @staticmethod
    async def _try_pytdbot_api(video_id: str, is_video: bool) -> Optional[str]:
        api_base = VIDEO_API_URL if (is_video and VIDEO_API_URL) else API_URL
        if not api_base or not CircuitBreaker.is_available(api_base):
            return None
        dest_ext = ".mp4" if is_video else ".mp3"
        dest_path = os.path.join(DOWNLOAD_DIR, f"{video_id}{dest_ext}")
        media_type = "video" if is_video else "audio"
        try:
            LOGGER(__name__).info(f"[YT-API] Attempting Pytdbot/QuickEarn API for {video_id}")
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                url = f"{api_base}/download"
                params = {"url": video_id, "type": media_type}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "")
                        if "json" in content_type:
                            data = await resp.json()
                            direct_link = data.get("download_url") or data.get("url") or data.get("link")
                            if direct_link and await _save_stream_to_file(session, direct_link, dest_path):
                                CircuitBreaker.record_success(api_base)
                                LOGGER(__name__).info(f"[YT-API] Pytdbot API JSON direct stream successful for {video_id}")
                                return dest_path
                        else:
                            with open(dest_path, "wb") as f:
                                async for chunk in resp.content.iter_chunked(131072):
                                    f.write(chunk)
                            if is_valid_media_file(dest_path):
                                CircuitBreaker.record_success(api_base)
                                LOGGER(__name__).info(f"[YT-API] Pytdbot API direct binary successful for {video_id}")
                                return dest_path
                            elif os.path.exists(dest_path):
                                os.remove(dest_path)
                    else:
                        CircuitBreaker.record_failure(api_base, status_code=resp.status)
        except Exception as e:
            err_cat, _ = classify_ytdl_error(e)
            CircuitBreaker.record_failure(api_base, error_type=err_cat)
            LOGGER(__name__).warning(f"[YT-API] Pytdbot API failed for {video_id}: {e}")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception:
                    pass
        return None

    @staticmethod
    async def _try_cobalt_api(video_id: str, is_video: bool) -> Optional[str]:
        cobalt_endpoints = []
        if SELF_HOSTED_COBALT_URL:
            cobalt_endpoints.append(SELF_HOSTED_COBALT_URL)
        cobalt_endpoints.extend([
            "https://api.cobalt.tools",
            "https://cobalt-api.kwippy.com",
            "https://cobalt.qtf.ai",
        ])

        dest_ext = ".mp4" if is_video else ".mp3"
        dest_path = os.path.join(DOWNLOAD_DIR, f"{video_id}{dest_ext}")
        target_url = f"https://www.youtube.com/watch?v={video_id}"

        for endpoint in cobalt_endpoints:
            if not CircuitBreaker.is_available(endpoint):
                continue
            try:
                LOGGER(__name__).info(f"[YT-API] Attempting Cobalt API ({endpoint}) for {video_id}")
                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                payload = {
                    "url": target_url,
                    "downloadMode": "auto" if is_video else "audio",
                    "audioFormat": "mp3",
                }
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.post(endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            direct_url = data.get("url")
                            if direct_url and await _save_stream_to_file(session, direct_url, dest_path):
                                CircuitBreaker.record_success(endpoint)
                                LOGGER(__name__).info(f"[YT-API] Cobalt API successful for {video_id}")
                                return dest_path
                        else:
                            CircuitBreaker.record_failure(endpoint, status_code=resp.status)
            except Exception as e:
                err_cat, _ = classify_ytdl_error(e)
                CircuitBreaker.record_failure(endpoint, error_type=err_cat)
                LOGGER(__name__).debug(f"[YT-API] Cobalt API instance ({endpoint}) failed for {video_id}: {e}")
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass
        return None

    @staticmethod
    async def _try_invidious_piped_api(video_id: str, is_video: bool) -> Optional[str]:
        invidious_instances = [
            f"https://pipedapi.kavin.rocks/streams/{video_id}",
            f"https://api.piped.video/streams/{video_id}",
            f"https://pipedapi.mha.fi/streams/{video_id}",
            f"https://yewtu.be/api/v1/videos/{video_id}",
            f"https://invidious.drgns.space/api/v1/videos/{video_id}",
            f"https://inv.riverside.rocks/api/v1/videos/{video_id}",
            f"https://invidious.nerdvpn.de/api/v1/videos/{video_id}",
        ]
        dest_ext = ".mp4" if is_video else ".mp3"
        dest_path = os.path.join(DOWNLOAD_DIR, f"{video_id}{dest_ext}")

        for inst in invidious_instances:
            try:
                LOGGER(__name__).info(f"[YT-API] Attempting Invidious/Piped API for {video_id}")
                async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                    async with session.get(inst, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            stream_url = None
                            if "adaptiveFormats" in data:
                                for fmt in data["adaptiveFormats"]:
                                    if not is_video and "audio" in fmt.get("type", ""):
                                        stream_url = fmt.get("url")
                                        break
                                    elif is_video and "video" in fmt.get("type", ""):
                                        stream_url = fmt.get("url")
                                        break
                            elif "audioStreams" in data and not is_video:
                                stream_url = data["audioStreams"][0].get("url")
                            elif "videoStreams" in data and is_video:
                                stream_url = data["videoStreams"][0].get("url")

                            if stream_url and await _save_stream_to_file(session, stream_url, dest_path):
                                LOGGER(__name__).info(f"[YT-API] Invidious/Piped API stream successful for {video_id}")
                                return dest_path
            except Exception as e:
                LOGGER(__name__).debug(f"[YT-API] Invidious/Piped instance failed for {video_id}: {e}")
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass
        return None

    @classmethod
    async def download_song(cls, link: str) -> Optional[str]:
        video_id = extract_video_id(link)
        if not video_id or len(video_id) < 3:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Invalid video_id extracted from link: {link}")
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        existing_file = find_downloaded_file(video_id, is_video=False)
        if existing_file:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Using cached media file for video_id: {video_id}")
            return existing_file

        # Step 0: Check JioSaavn Cache
        if video_id in _JIOSAAVN_CACHE:
            stream_url = _JIOSAAVN_CACHE[video_id]
            LOGGER(__name__).info(f"[JIOSAAVN-PLAY] Using cached direct JioSaavn stream URL for {video_id}: {stream_url}")
            return stream_url

        # Step 1: External API System (Sequential Multi-Source Fallback Pipeline)
        api_providers = [
            cls._try_jiosaavn_api,
            cls._try_shruti_api,
            cls._try_pytdbot_api,
            cls._try_cobalt_api,
            cls._try_invidious_piped_api,
        ]

        for provider in api_providers:
            try:
                res_path = await provider(video_id, is_video=False)
                if res_path and (res_path.startswith("http://") or res_path.startswith("https://") or is_valid_media_file(res_path)):
                    return res_path
            except Exception as e:
                LOGGER(__name__).debug(f"[YT-API] API provider error: {e}")

        # Step 2: Multi-Method Local yt-dlp Sequential Download Pipeline
        yt_link = f"https://www.youtube.com/watch?v={video_id}"
        loop = asyncio.get_event_loop()
        valid_cookie_files = get_valid_cookie_files()
        primary_cookie = valid_cookie_files[0] if valid_cookie_files else None

        modes = [
            ("mweb_pot_nocookies", ["mweb"], None, True),
            ("default_pot_nocookies", ["mweb", "ios", "android", "web"], None, True),
            ("mweb_cookies", ["mweb"], primary_cookie, False),
            ("default_cookies", ["mweb", "web", "ios", "android"], primary_cookie, False),
            ("web_safari_emergency", ["web_safari", "mweb", "web"], primary_cookie, False),
        ]

        for mode_name, clients, cookie_file, use_pot in modes:
            for retry in range(1, 3):
                try:
                    c_label = os.path.basename(cookie_file) if cookie_file else "no-cookies"
                    LOGGER(__name__).info(f"[YT-PIPELINE] Trying mode '{mode_name}' (attempt {retry}/2, cookie={c_label}) for {video_id}")
                    ydl_opts = get_ytdl_base_opts(cookie_file=cookie_file, is_video=False)
                    yt_args = {"player_client": clients}
                    if use_pot and is_bgutil_server_running() and POT_PROVIDER_URL:
                        yt_args["po_token"] = [f"web+{POT_PROVIDER_URL}"]
                    ydl_opts["extractor_args"] = {"youtube": yt_args}
                    ydl_opts["outtmpl"] = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")

                    await loop.run_in_executor(
                        None, lambda opts=ydl_opts: yt_dlp.YoutubeDL(opts).download([yt_link])
                    )
                    downloaded = find_downloaded_file(video_id, is_video=False)
                    if downloaded:
                        LOGGER(__name__).info(f"[YT-PIPELINE] Mode '{mode_name}' successful for {video_id}")
                        AudioCache.set(video_id=video_id, local_path=downloaded, source="youtube")
                        return downloaded
                except Exception as e:
                    err_cat, err_msg = classify_ytdl_error(e)
                    LOGGER(__name__).warning(f"[YT-PIPELINE] Mode '{mode_name}' attempt {retry} failed ({err_cat}): {err_msg}")
                    if cookie_file and err_cat in ("BOT_CHECK", "AUTH_REQUIRED"):
                        mark_cookie_unusable(cookie_file)
                        break  # Stop retrying with unusable cookie
                    if err_cat == "FORMAT_ERROR":
                        # Retry with relaxed format in next iteration or next mode
                        pass
                    downloaded = find_downloaded_file(video_id, is_video=False)
                    if downloaded:
                        AudioCache.set(video_id=video_id, local_path=downloaded, source="youtube")
                        return downloaded

        # Final Fallback: JioSaavn query retry
        LOGGER(__name__).info(f"[YT-DOWNLOAD] Triggering final JioSaavn search/download fallback for {video_id}")
        title, _, dur_sec, _, _ = await YouTube.details(video_id, videoid=True)
        js_res = await cls._try_jiosaavn_api(video_id, is_video=False, title=title, duration_sec=dur_sec)
        if js_res:
            return js_res

        LOGGER(__name__).critical(f"[YT-DOWNLOAD] All audio download pipelines failed for video_id: {video_id}")
        return None

    @classmethod
    async def download_video(cls, link: str) -> Optional[str]:
        video_id = extract_video_id(link)
        if not video_id or len(video_id) < 3:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Invalid video_id extracted: {link}")
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        existing_file = find_downloaded_file(video_id, is_video=True)
        if existing_file:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Using cached video file for video_id: {video_id}")
            return existing_file

        # Step 1: External API Video Providers
        api_providers = [
            cls._try_shruti_api,
            cls._try_pytdbot_api,
            cls._try_cobalt_api,
            cls._try_invidious_piped_api,
        ]

        for provider in api_providers:
            try:
                res_path = await provider(video_id, is_video=True)
                if res_path and is_valid_media_file(res_path):
                    return res_path
            except Exception as e:
                LOGGER(__name__).debug(f"[YT-API] API video provider error: {e}")

        # Step 2: Local yt-dlp Video Multi-Cookie
        yt_link = f"https://www.youtube.com/watch?v={video_id}"
        valid_cookie_files = get_valid_cookie_files()
        loop = asyncio.get_event_loop()

        if valid_cookie_files:
            for idx, cookie_file in enumerate(valid_cookie_files, 1):
                try:
                    LOGGER(__name__).info(f"[YT-DOWNLOAD] Local yt-dlp video (Cookie #{idx}) for {video_id}")
                    ydl_opts = get_ytdl_base_opts(cookie_file=cookie_file, is_video=True)
                    ydl_opts.update({
                        "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
                    })
                    await loop.run_in_executor(
                        None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([yt_link])
                    )
                    downloaded = find_downloaded_file(video_id, is_video=True)
                    if downloaded:
                        return downloaded
                except Exception as e:
                    err_type, err_msg = classify_ytdl_error(e)
                    if err_type in ("BOT_CHECK", "AUTH_REQUIRED"):
                        mark_cookie_unusable(cookie_file)
                    LOGGER(__name__).warning(f"[YT-AUTH] Video cookie #{idx} failed ({err_type}) for {video_id}: {err_msg}")

        # Step 3: Local yt-dlp Video No-Cookie
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Local yt-dlp video (no cookies) for {video_id}")
            ydl_opts_nocookie = get_ytdl_base_opts(cookie_file=None, is_video=True)
            ydl_opts_nocookie.update({
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
            })
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(ydl_opts_nocookie).download([yt_link])
            )
            downloaded = find_downloaded_file(video_id, is_video=True)
            if downloaded:
                return downloaded
        except Exception as e:
            LOGGER(__name__).error(f"[YT-DOWNLOAD] Video download (no cookies) failed for {video_id}: {e}")

        # Step 4: Automatic Fallback to Audio Download to Guarantee Song Playback
        LOGGER(__name__).warning(f"[YT-DOWNLOAD] All video extraction methods failed for {video_id}. Falling back to audio mode to prevent playback failure.")
        audio_file = await cls.download_song(link)
        if audio_file:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Audio-only fallback successful for video request {video_id}")
            return audio_file

        LOGGER(__name__).critical(f"[YT-DOWNLOAD] All video and audio fallbacks failed for video_id: {video_id}")
        return None


async def download_song(link: str) -> Optional[str]:
    return await YouTubeExtractor.download_song(link)


async def download_video(link: str) -> Optional[str]:
    return await YouTubeExtractor.download_video(link)


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def _oembed_details(self, vidid: str) -> Tuple[str, str]:
        try:
            url = f"{self.base}{vidid}"
            oembed_url = f"{self.status}{url}&format=json"
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                async with session.get(oembed_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        title = data.get("title", "Unknown Title")
                        thumbnail = data.get("thumbnail_url", f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg")
                        return title, thumbnail
        except Exception as e:
            LOGGER(__name__).error(f"[YT-EXTRACT] oEmbed fetch error for {vidid}: {e}")
        return "Unknown Title", f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"

    async def _jiosaavn_extract_track_info(self, query: str) -> Optional[Tuple[Dict[str, Any], str]]:
        if "youtube.com" in query or "youtu.be" in query:
            return None
        try:
            info = await JioSaavn.search_song(query)
            if info and info.get("stream_url"):
                title = info.get("title", query)
                song_id = info.get("id") or "saavn_track"
                duration_min = info.get("duration_min", "3:30")
                thumb = info.get("thumb", "https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg")
                stream_url = info.get("stream_url")
                track_details = {
                    "title": title,
                    "link": f"https://www.youtube.com/watch?v={song_id}",
                    "vidid": song_id,
                    "duration_min": duration_min,
                    "thumb": thumb,
                    "stream_url": stream_url,
                }
                _JIOSAAVN_CACHE[song_id] = stream_url
                LOGGER(__name__).info(f"[JIOSAAVN-SEARCH] Track resolved via JioSaavn API: {title} ({song_id}) -> {stream_url}")
                return track_details, song_id
        except Exception as e:
            LOGGER(__name__).warning(f"[JIOSAAVN-SEARCH] JioSaavn track extraction failed: {e}")
        return None

    async def _ytdl_extract_track_info(self, query_or_url: str) -> Optional[Tuple[Dict[str, Any], str]]:
        loop = asyncio.get_event_loop()
        valid_cookie_files = get_valid_cookie_files()
        cookie_candidates = valid_cookie_files + [None]
        target = query_or_url if ("youtube.com" in query_or_url or "youtu.be" in query_or_url) else f"ytsearch5:{query_or_url}"

        for idx, cookie_file in enumerate(cookie_candidates, 1):
            ydl_opts = get_ytdl_base_opts(cookie_file=cookie_file)
            def _extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(target, download=False)

            try:
                c_desc = os.path.basename(cookie_file) if cookie_file else "no-cookies"
                LOGGER(__name__).info(f"[YT-SEARCH] Extracting info using candidate #{idx} ({c_desc}) for: {query_or_url}")
                info = await loop.run_in_executor(None, _extract)
                if info:
                    entries = info.get("entries") if "entries" in info else [info]
                    for entry in (entries or []):
                        if not entry:
                            continue
                        v_id = entry.get("id")
                        if not v_id:
                            continue
                        title = entry.get("title", "Unknown Track")
                        duration_sec = int(entry.get("duration") or 0)
                        duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "0:00"
                        thumbnail = entry.get("thumbnail") or f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg"
                        yturl = f"https://www.youtube.com/watch?v={v_id}"
                        track_details = {
                            "title": title,
                            "link": yturl,
                            "vidid": v_id,
                            "duration_min": duration_min,
                            "thumb": thumbnail,
                        }
                        LOGGER(__name__).info(f"[YT-SEARCH] Successfully resolved track: {title} ({v_id})")
                        return track_details, v_id
            except Exception as e:
                err_type, err_msg = classify_ytdl_error(e)
                if cookie_file and err_type in ("BOT_CHECK", "AUTH_REQUIRED"):
                    mark_cookie_unusable(cookie_file)
                LOGGER(__name__).warning(f"[YT-EXTRACT] Candidate #{idx} error ({err_type}) for {query_or_url}: {err_msg}")
        return None

    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        vidid = extract_video_id(link)

        # Primary Search Option: JioSaavn Search API for audio track resolution
        if not ("youtube.com" in link or "youtu.be" in link):
            js_res = await self._jiosaavn_extract_track_info(link)
            if js_res:
                details_dict, v_id = js_res
                duration_sec = time_to_seconds(details_dict["duration_min"])
                return details_dict["title"], details_dict["duration_min"], duration_sec, details_dict["thumb"], v_id

        # Fallback Multi-Result Search: VideosSearch
        if VideosSearch is not None and not ("youtube.com" in link or "youtu.be" in link):
            try:
                LOGGER(__name__).info(f"[YT-SEARCH] Searching multiple results via VideosSearch for: {link}")
                results = VideosSearch(link, limit=5)
                res = await results.next()
                if res.get("result"):
                    for result in res["result"]:
                        if not result or not result.get("id"):
                            continue
                        title = result.get("title", "Unknown Title")
                        duration_min = result.get("duration", "0:00")
                        thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
                        v_id = result["id"]
                        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
                        LOGGER(__name__).info(f"[YT-SEARCH] Found candidate via VideosSearch: {title} ({v_id})")
                        return title, duration_min, duration_sec, thumbnail, v_id
            except Exception as e:
                LOGGER(__name__).error(f"[YT-SEARCH] VideosSearch details error: {e}")

        # Fallback 1: yt-dlp metadata extraction
        yt_res = await self._ytdl_extract_track_info(link)
        if yt_res:
            details_dict, v_id = yt_res
            duration_sec = time_to_seconds(details_dict["duration_min"])
            return details_dict["title"], details_dict["duration_min"], duration_sec, details_dict["thumb"], v_id

        # Fallback 2: JioSaavn Search API
        js_res = await self._jiosaavn_extract_track_info(link)
        if js_res:
            details_dict, v_id = js_res
            duration_sec = time_to_seconds(details_dict["duration_min"])
            return details_dict["title"], details_dict["duration_min"], duration_sec, details_dict["thumb"], v_id

        # Fallback 3: oEmbed details
        title, thumbnail = await self._oembed_details(vidid)
        return title, "0:00", 0, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        title, _, _, _, _ = await self.details(link, videoid)
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        _, duration_min, _, _, _ = await self.details(link, videoid)
        return duration_min

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        _, _, _, thumbnail, _ = await self.details(link, videoid)
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            LOGGER(__name__).error(f"[YT-DOWNLOAD] YouTube.video error: {e}\n{traceback.format_exc()}")
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        if Playlist is None:
            return []
        try:
            plist = await Playlist.get(link)
            videos = plist.get("videos") or []
            ids = []
            for data in videos[:limit]:
                if not data:
                    continue
                vid = data.get("id")
                if not vid:
                    continue
                ids.append(vid)
            return ids
        except Exception as e:
            LOGGER(__name__).error(f"[YT-EXTRACT] YouTube.playlist error: {e}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        vidid = extract_video_id(link)

        # Priority 1: JioSaavn Search API for direct song resolution
        if not ("youtube.com" in link or "youtu.be" in link):
            js_res = await self._jiosaavn_extract_track_info(link)
            if js_res:
                return js_res

        # Priority 2: Multi-result search via VideosSearch if it's a search term
        if VideosSearch is not None and not ("youtube.com" in link or "youtu.be" in link):
            try:
                LOGGER(__name__).info(f"[YT-SEARCH] Multi-result track search for: '{link}'")
                results = VideosSearch(link, limit=5)
                res = await results.next()
                if res.get("result"):
                    for result in res["result"]:
                        if not result or not result.get("id"):
                            continue
                        title = result["title"]
                        duration_min = result.get("duration", "0:00")
                        v_id = result["id"]
                        yturl = result.get("link", f"https://www.youtube.com/watch?v={v_id}")
                        thumbnail = result["thumbnails"][0]["url"].split("?")[0] if result.get("thumbnails") else f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg"
                        track_details = {
                            "title": title,
                            "link": yturl,
                            "vidid": v_id,
                            "duration_min": duration_min,
                            "thumb": thumbnail,
                        }
                        LOGGER(__name__).info(f"[YT-SEARCH] Selected track candidate: {title} ({v_id})")
                        return track_details, v_id
            except Exception as e:
                LOGGER(__name__).error(f"[YT-SEARCH] YouTube.track VideosSearch error for '{link}': {e}")

        # Fallback 1: yt-dlp metadata extraction
        yt_res = await self._ytdl_extract_track_info(link)
        if yt_res:
            return yt_res

        # Fallback 2: JioSaavn Search API
        js_res = await self._jiosaavn_extract_track_info(link)
        if js_res:
            return js_res

        # Fallback 3: oEmbed details
        title, thumbnail = await self._oembed_details(vidid)
        yturl = f"https://www.youtube.com/watch?v={vidid}"
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": "0:00",
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        valid_cookie_files = get_valid_cookie_files()
        cookie_candidates = valid_cookie_files + [None]
        formats_available = []

        loop = asyncio.get_event_loop()
        for idx, cookie_file in enumerate(cookie_candidates, 1):
            ytdl_opts = get_ytdl_base_opts(cookie_file=cookie_file)
            def _extract_formats():
                with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                    return ydl.extract_info(link, download=False)
            try:
                r = await loop.run_in_executor(None, _extract_formats)
                if r:
                    for format in r.get("formats", []):
                        try:
                            if "dash" not in str(format.get("format", "")).lower():
                                formats_available.append(
                                    {
                                        "format": format.get("format"),
                                        "filesize": format.get("filesize"),
                                        "format_id": format.get("format_id"),
                                        "ext": format.get("ext"),
                                        "format_note": format.get("format_note", ""),
                                        "yturl": link,
                                    }
                                )
                        except Exception:
                            continue
                    if formats_available:
                        return formats_available, link
            except Exception as e:
                err_type, _ = classify_ytdl_error(e)
                if cookie_file and err_type in ("BOT_CHECK", "AUTH_REQUIRED"):
                    mark_cookie_unusable(cookie_file)
                LOGGER(__name__).error(f"[YT-EXTRACT] YouTube.formats candidate #{idx} error: {e}")
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        if VideosSearch is not None:
            try:
                a = VideosSearch(link, limit=10)
                res = await a.next()
                result = res.get("result", [])
                if len(result) > query_type:
                    title = result[query_type]["title"]
                    duration_min = result[query_type]["duration"]
                    vidid = result[query_type]["id"]
                    thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
                    return title, duration_min, thumbnail, vidid
            except Exception as e:
                LOGGER(__name__).error(f"[YT-SEARCH] YouTube.slider error: {e}")

        vidid = extract_video_id(link)
        title, thumbnail = await self._oembed_details(vidid)
        return title, "0:00", thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        is_song_downloader = bool(songaudio or songvideo)
        try:
            if video or songvideo:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)

            if not downloaded_file and (video or songvideo):
                LOGGER(__name__).info("[YT-DOWNLOAD] Video download failed, retrying in audio mode...")
                downloaded_file = await download_song(link)

            if not downloaded_file:
                if is_song_downloader:
                    raise Exception("All download fallbacks failed for track")
                else:
                    return None, False

            if is_song_downloader:
                return downloaded_file
            else:
                return downloaded_file, True
        except Exception as e:
            LOGGER(__name__).error(f"[YT-DOWNLOAD] YouTube.download error: {e}\n{traceback.format_exc()}")
            if is_song_downloader:
                raise e
            else:
                return None, False


YouTube = YouTubeAPI()
