import asyncio
import os
import re
import traceback
from typing import Union, Optional, Tuple, Dict, Any, List
import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

try:
    from pytubefix import YouTube as PytubeFixYT
except ImportError:
    PytubeFixYT = None

try:
    from py_yt import VideosSearch, Playlist
except ImportError:
    try:
        from youtubesearchpython.__future__ import VideosSearch, Playlist
    except ImportError:
        VideosSearch = None
        Playlist = None

import config
from SONALI_MUSIC import LOGGER
from SONALI_MUSIC.utils.youtube_utils import (
    classify_ytdl_error,
    CircuitBreaker,
    AudioCache,
    get_next_cookie_file,
    is_cookie_usable as is_cookie_file_usable,
    mark_cookie_unusable,
)

_JIOSAAVN_CACHE: Dict[str, str] = {}
DOWNLOAD_DIR = os.path.abspath("downloads")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


def is_cookie_usable(cookie_file: Optional[str] = None) -> bool:
    if cookie_file:
        return is_cookie_file_usable(cookie_file)
    cookie = get_next_cookie_file()
    return bool(cookie and is_cookie_file_usable(cookie))


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
        async with session.get(url, headers=req_headers, timeout=aiohttp.ClientTimeout(total=120), ssl=False) as resp:
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


async def get_youtube_stream(video_id: str, url: Optional[str] = None) -> Optional[str]:
    """
    100% Zero-Cookie YouTube-ONLY Audio Extraction via Asynchronous Multi-Layer Fallback Chain.

    LAYER 1: yt-dlp Mobile Client Spoofing (Primary)
    LAYER 2: pytubefix (Backup 1)
    LAYER 3: Cobalt API Stream Fetcher (Backup 2)
    LAYER 4: Invidious / Piped API (Last Resort)
    """
    if not video_id and url:
        video_id = extract_video_id(url)
    if not video_id:
        LOGGER(__name__).warning("[YT-STREAM] get_youtube_stream called with empty video_id")
        return None

    target_url = url or f"https://www.youtube.com/watch?v={video_id}"
    LOGGER(__name__).info(f"[YT-STREAM] Initiating YouTube extraction chain for video_id: {video_id}")

    # LAYER 1: yt-dlp Mobile Client Spoofing + Rotated Cookie (Primary)
    cookie_file = get_next_cookie_file()
    try:
        LOGGER(__name__).info(f"[YT-STREAM:L1] Attempting yt-dlp mobile client spoofing with cookie ({os.path.basename(cookie_file) if cookie_file else 'none'}) for {video_id}")
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android_vr", "mweb"],
                    "player_skip": ["webpage", "configs"],
                }
            },
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
        }
        if cookie_file:
            ydl_opts["cookiefile"] = os.path.abspath(cookie_file)

        def _extract_l1():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(target_url, download=False)

        info = await asyncio.wait_for(asyncio.to_thread(_extract_l1), timeout=12)
        if info:
            stream_url = None
            if "formats" in info and isinstance(info["formats"], list):
                for fmt in info["formats"]:
                    if fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") in (None, "none") and fmt.get("url"):
                        stream_url = fmt["url"]
                        break
            if not stream_url:
                stream_url = info.get("url")
            if not stream_url and "formats" in info and isinstance(info["formats"], list) and info["formats"]:
                stream_url = info["formats"][-1].get("url")
            if stream_url:
                LOGGER(__name__).info(f"[YT-STREAM:L1] Success! Direct stream retrieved for {video_id}")
                return stream_url
    except Exception as e:
        err_cat, err_msg = classify_ytdl_error(e)
        if cookie_file and err_cat in ("BOT_CHECK", "AUTH_REQUIRED"):
            mark_cookie_unusable(cookie_file, f"{err_cat}: {err_msg}")
        LOGGER(__name__).warning(f"[YT-STREAM:L1] Layer 1 (yt-dlp) failed for {video_id}: {e}")

    # LAYER 2: pytubefix (Backup 1)
    if PytubeFixYT is not None:
        try:
            LOGGER(__name__).info(f"[YT-STREAM:L2] Attempting pytubefix for {video_id}")

            def _extract_l2():
                for client_type in ["WEB", "ANDROID"]:
                    try:
                        yt = PytubeFixYT(target_url, client=client_type)
                        audio_stream = yt.streams.get_audio_only()
                        if audio_stream and audio_stream.url:
                            return audio_stream.url
                    except Exception as inner_e:
                        LOGGER(__name__).debug(f"[YT-STREAM:L2] Client '{client_type}' failed: {inner_e}")
                return None

            stream_url = await asyncio.wait_for(asyncio.to_thread(_extract_l2), timeout=10)
            if stream_url:
                LOGGER(__name__).info(f"[YT-STREAM:L2] Success! pytubefix stream retrieved for {video_id}")
                return stream_url
        except Exception as e:
            LOGGER(__name__).warning(f"[YT-STREAM:L2] Layer 2 (pytubefix) failed for {video_id}: {e}")

    # LAYER 3: Cobalt API Stream Fetcher (Backup 2)
    try:
        LOGGER(__name__).info(f"[YT-STREAM:L3] Attempting Cobalt API stream fetch for {video_id}")
        cobalt_instances = [
            "https://api.cobalt.tools/api/json",
            "https://cobalt-api.kwippy.com/api/json",
            "https://cobalt.qtf.ai/api/json",
        ]
        self_hosted = getattr(config, "SELF_HOSTED_COBALT_URL", None)
        if self_hosted:
            ep = self_hosted.rstrip('/')
            if not ep.endswith('/api/json'):
                ep += '/api/json'
            cobalt_instances.insert(0, ep)

        payload = {
            "url": target_url,
            "aFormat": "mp3",
            "isAudioOnly": True,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            for instance in cobalt_instances:
                try:
                    async with session.post(instance, json=payload, timeout=timeout) as resp:
                        if resp.status in (200, 201):
                            data = await resp.json()
                            direct_url = data.get("url") or data.get("audio")
                            if direct_url:
                                LOGGER(__name__).info(f"[YT-STREAM:L3] Success! Cobalt API stream retrieved from {instance} for {video_id}")
                                return direct_url
                except Exception as inst_err:
                    LOGGER(__name__).debug(f"[YT-STREAM:L3] Instance {instance} error for {video_id}: {inst_err}")
    except Exception as e:
        LOGGER(__name__).warning(f"[YT-STREAM:L3] Layer 3 (Cobalt) failed for {video_id}: {e}")

    # LAYER 4: Invidious / Piped API (Last Resort)
    try:
        LOGGER(__name__).info(f"[YT-STREAM:L4] Attempting Invidious/Piped API for {video_id}")
        piped_endpoints = [
            f"https://pipedapi.kavin.rocks/streams/{video_id}",
            f"https://api.piped.video/streams/{video_id}",
            f"https://pipedapi.mha.fi/streams/{video_id}",
            f"https://yewtu.be/api/v1/videos/{video_id}",
            f"https://invidious.drgns.space/api/v1/videos/{video_id}",
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            for ep in piped_endpoints:
                try:
                    async with session.get(ep, timeout=timeout) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            audio_streams = data.get("audioStreams", [])
                            if not audio_streams and "adaptiveFormats" in data:
                                audio_streams = [
                                    fmt for fmt in data.get("adaptiveFormats", [])
                                    if "audio" in fmt.get("type", "") or fmt.get("acodec") not in (None, "none")
                                ]
                            if audio_streams:
                                sorted_streams = sorted(
                                    audio_streams,
                                    key=lambda s: int(s.get("bitrate") or s.get("bitrate_num") or 0),
                                    reverse=True,
                                )
                                best_audio_url = sorted_streams[0].get("url")
                                if best_audio_url:
                                    LOGGER(__name__).info(f"[YT-STREAM:L4] Success! Invidious/Piped stream retrieved from {ep} for {video_id}")
                                    return best_audio_url
                except Exception as ep_err:
                    LOGGER(__name__).debug(f"[YT-STREAM:L4] Endpoint {ep} error for {video_id}: {ep_err}")
    except Exception as e:
        LOGGER(__name__).warning(f"[YT-STREAM:L4] Layer 4 (Invidious/Piped) failed for {video_id}: {e}")

    LOGGER(__name__).error(f"[YT-STREAM] All 4 extraction layers failed for {video_id}")
    return None


class YouTubeExtractor:
    """Zero-Cookie YouTube-ONLY Audio & Video Extraction Pipeline."""

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

        yt_link = f"https://www.youtube.com/watch?v={video_id}"
        stream_url = await get_youtube_stream(video_id, yt_link)

        if stream_url and (stream_url.startswith("http://") or stream_url.startswith("https://")):
            dest_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, connector=connector) as session:
                saved = await _save_stream_to_file(session, stream_url, dest_path)
                if saved:
                    AudioCache.set(video_id=video_id, local_path=dest_path, source="youtube")
                    return dest_path

        # Fallback 1: Direct yt-dlp local audio download
        cookie_file = get_next_cookie_file()
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Fallback 1: Direct yt-dlp local download for video_id: {video_id}")
            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            if cookie_file:
                ydl_opts["cookiefile"] = os.path.abspath(cookie_file)

            def _dl_ytdl():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([yt_link])

            await asyncio.to_thread(_dl_ytdl)
            dl_file = find_downloaded_file(video_id, is_video=False)
            if dl_file:
                AudioCache.set(video_id=video_id, local_path=dl_file, source="youtube")
                return dl_file
        except Exception as e:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Fallback 1 (yt-dlp) failed for {video_id}: {e}")

        # Fallback 2: JioSaavn API audio search and download
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Fallback 2: JioSaavn API search and download for video_id: {video_id}")
            from SONALI_MUSIC.platforms.Jiosaavn import JioSaavn
            track_title = video_id
            try:
                title_res, _ = await YouTube._oembed_details(video_id)
                if title_res and title_res != "Unknown Title":
                    track_title = title_res
            except Exception:
                pass

            saavn_file = await JioSaavn.download_song_by_query(
                query=track_title,
                dest_filename=f"{video_id}.mp3",
                target_title=track_title,
            )
            if saavn_file and is_valid_media_file(saavn_file):
                AudioCache.set(video_id=video_id, local_path=saavn_file, source="jiosaavn")
                return saavn_file

            song_info = await JioSaavn.search_song(query=track_title, target_title=track_title)
            if song_info and song_info.get("stream_url"):
                s_url = song_info["stream_url"]
                _JIOSAAVN_CACHE[video_id] = s_url
                AudioCache.set(video_id=video_id, local_path=s_url, source="jiosaavn")
                return s_url
        except Exception as saavn_err:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Fallback 2 (JioSaavn) failed for {video_id}: {saavn_err}")

        if stream_url:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Returning raw stream_url as last resort for {video_id}")
            AudioCache.set(video_id=video_id, local_path=stream_url, source="youtube")
            return stream_url

        LOGGER(__name__).error(f"[YT-DOWNLOAD] All extraction layers and fallbacks failed for video_id: {video_id}")
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

        yt_link = f"https://www.youtube.com/watch?v={video_id}"
        cookie_file = get_next_cookie_file()

        try:
            ydl_opts = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios", "android_vr", "mweb"],
                        "player_skip": ["webpage", "configs"],
                    }
                },
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            if cookie_file:
                ydl_opts["cookiefile"] = os.path.abspath(cookie_file)

            def _dl_vid():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([yt_link])

            await asyncio.to_thread(_dl_vid)
            downloaded = find_downloaded_file(video_id, is_video=True)
            if downloaded:
                return downloaded
        except Exception as e:
            err_cat, err_msg = classify_ytdl_error(e)
            if cookie_file and err_cat in ("BOT_CHECK", "AUTH_REQUIRED"):
                mark_cookie_unusable(cookie_file, f"{err_cat}: {err_msg}")
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Video extraction failed for {video_id}: {e}")

        LOGGER(__name__).warning(f"[YT-DOWNLOAD] Video extraction failed for {video_id}. Falling back to audio mode.")
        return await cls.download_song(link)


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

    async def _ytdl_extract_track_info(self, query_or_url: str) -> Optional[Tuple[Dict[str, Any], str]]:
        target = query_or_url if ("youtube.com" in query_or_url or "youtu.be" in query_or_url) else f"ytsearch5:{query_or_url}"
        cookie_file = get_next_cookie_file()
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android_vr", "mweb"],
                    "player_skip": ["webpage", "configs"],
                }
            },
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
        }
        if cookie_file:
            ydl_opts["cookiefile"] = os.path.abspath(cookie_file)

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(target, download=False)

        try:
            info = await asyncio.to_thread(_extract)
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
                mark_cookie_unusable(cookie_file, f"{err_type}: {err_msg}")
            LOGGER(__name__).warning(f"[YT-EXTRACT] Track search error ({err_type}) for {query_or_url}: {err_msg}")
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

        yt_res = await self._ytdl_extract_track_info(link)
        if yt_res:
            details_dict, v_id = yt_res
            duration_sec = time_to_seconds(details_dict["duration_min"])
            return details_dict["title"], details_dict["duration_min"], duration_sec, details_dict["thumb"], v_id

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

        yt_res = await self._ytdl_extract_track_info(link)
        if yt_res:
            return yt_res

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

        cookie_file = get_next_cookie_file()
        formats_available = []
        ydl_opts = {
            "format": "bestaudio/best",
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "android_vr", "mweb"],
                    "player_skip": ["webpage", "configs"],
                }
            },
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
        }
        if cookie_file:
            ydl_opts["cookiefile"] = os.path.abspath(cookie_file)

        def _extract_formats():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(link, download=False)

        try:
            r = await asyncio.to_thread(_extract_formats)
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
        except Exception as e:
            err_cat, err_msg = classify_ytdl_error(e)
            if cookie_file and err_cat in ("BOT_CHECK", "AUTH_REQUIRED"):
                mark_cookie_unusable(cookie_file, f"{err_cat}: {err_msg}")
            LOGGER(__name__).error(f"[YT-EXTRACT] YouTube.formats error: {e}")

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
