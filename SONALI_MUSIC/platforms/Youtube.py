import asyncio
import os
import re
import traceback
from typing import Union, Optional, Tuple, Dict, Any, List
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
import aiohttp
from SONALI_MUSIC import LOGGER
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
)

try:
    from py_yt import VideosSearch, Playlist
except ImportError:
    try:
        from youtubesearchpython.__future__ import VideosSearch, Playlist
    except ImportError:
        VideosSearch = None
        Playlist = None

API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.site")
API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotsjyOuNr6aH5inWY06YDYJ")

DOWNLOAD_DIR = os.path.abspath("downloads")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


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




class YouTubeExtractor:
    """Centralized YouTube Extraction & Fallback Service with Multi-Cookie Rotation."""

    @staticmethod
    async def download_song(link: str) -> Optional[str]:
        video_id = extract_video_id(link)
        if not video_id or len(video_id) < 3:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Invalid video_id extracted from link: {link}")
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        existing_file = find_downloaded_file(video_id, is_video=False)
        if existing_file:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Using cached media file for video_id: {video_id}")
            return existing_file

        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

        # Attempt A: Shruti External API
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt A: External API download for {video_id}")
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                async with session.get(
                    f"{API_URL}/download",
                    params={"url": video_id, "type": "audio", "api_key": API_KEY},
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    if resp.status == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                        if is_valid_media_file(file_path):
                            LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt A successful for {video_id}")
                            return file_path
                        else:
                            if os.path.exists(file_path):
                                os.remove(file_path)
        except Exception as e:
            LOGGER(__name__).error(f"[YT-DOWNLOAD] Attempt A (API) failed for {video_id}: {e}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        yt_link = f"https://www.youtube.com/watch?v={video_id}"
        valid_cookie_files = get_valid_cookie_files()
        loop = asyncio.get_event_loop()

        # Attempt B (Multi-Cookie Loop): Try each available valid cookie dataset sequentially
        if valid_cookie_files:
            for idx, cookie_file in enumerate(valid_cookie_files, 1):
                try:
                    LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt B (Cookie #{idx} - {os.path.basename(cookie_file)}): yt-dlp download for {video_id}")
                    ydl_opts = get_ytdl_base_opts(cookie_file=cookie_file, is_video=False)
                    ydl_opts.update({
                        "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
                    })
                    if get_ffmpeg_path():
                        ydl_opts["postprocessors"] = [
                            {
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "192",
                            }
                        ]
                    await loop.run_in_executor(
                        None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([yt_link])
                    )
                    downloaded = find_downloaded_file(video_id, is_video=False)
                    if downloaded:
                        LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt B (Cookie #{idx}) successful for {video_id}")
                        return downloaded
                except Exception as e:
                    err_type, err_msg = classify_ytdl_error(e)
                    if err_type in ("BOT_CHECK", "AUTH_REQUIRED"):
                        mark_cookie_unusable(cookie_file)
                    LOGGER(__name__).warning(f"[YT-AUTH] Attempt B (Cookie #{idx} - {os.path.basename(cookie_file)}) failed ({err_type}) for {video_id}: {err_msg}")
                    downloaded = find_downloaded_file(video_id, is_video=False)
                    if downloaded:
                        LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt B (Cookie #{idx}) retrieved downloaded media file despite postprocessing error for {video_id}")
                        return downloaded

        # Attempt C & D: yt-dlp without cookies
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt C/D: yt-dlp bestaudio (no cookies) for {video_id}")
            ydl_opts_nocookie = get_ytdl_base_opts(cookie_file=None, is_video=False)
            ydl_opts_nocookie.update({
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
            })
            if get_ffmpeg_path():
                ydl_opts_nocookie["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(ydl_opts_nocookie).download([yt_link])
            )
            downloaded = find_downloaded_file(video_id, is_video=False)
            if downloaded:
                LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt C/D successful for {video_id}")
                return downloaded
        except Exception as e:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Attempt C/D failed for {video_id}: {e}")
            downloaded = find_downloaded_file(video_id, is_video=False)
            if downloaded:
                LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt C/D retrieved downloaded file despite postprocessing error for {video_id}")
                return downloaded

        # Attempt E: Raw audio format fallback without postprocessing
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt E: Raw audio fallback for {video_id}")
            ydl_opts_raw = get_ytdl_base_opts(cookie_file=None, is_video=False)
            ydl_opts_raw.update({
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
            })
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(ydl_opts_raw).download([yt_link])
            )
            downloaded = find_downloaded_file(video_id, is_video=False)
            if downloaded:
                LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt E successful for {video_id}")
                return downloaded
        except Exception as e:
            LOGGER(__name__).error(f"[YT-DOWNLOAD] Attempt E failed for {video_id}: {e}")
            downloaded = find_downloaded_file(video_id, is_video=False)
            if downloaded:
                return downloaded

        LOGGER(__name__).critical(f"[YT-DOWNLOAD] All download fallbacks failed for video_id: {video_id}")
        return None

    @staticmethod
    async def download_video(link: str) -> Optional[str]:
        video_id = extract_video_id(link)
        if not video_id or len(video_id) < 3:
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Invalid video_id extracted: {link}")
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        existing_file = find_downloaded_file(video_id, is_video=True)
        if existing_file:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Using cached video file for video_id: {video_id}")
            return existing_file

        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

        # Attempt A: Shruti API Video
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt A: External API video download for {video_id}")
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                async with session.get(
                    f"{API_URL}/download",
                    params={"url": video_id, "type": "video", "api_key": API_KEY},
                    timeout=aiohttp.ClientTimeout(total=600)
                ) as resp:
                    if resp.status == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                        if is_valid_media_file(file_path):
                            LOGGER(__name__).info(f"[YT-DOWNLOAD] External API video download successful for {video_id}")
                            return file_path
                        else:
                            if os.path.exists(file_path):
                                os.remove(file_path)
        except Exception as e:
            LOGGER(__name__).error(f"[YT-DOWNLOAD] External API video download failed for {video_id}: {e}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        yt_link = f"https://www.youtube.com/watch?v={video_id}"
        valid_cookie_files = get_valid_cookie_files()
        loop = asyncio.get_event_loop()

        # Attempt B (Multi-Cookie Loop): Try each available valid cookie dataset sequentially
        if valid_cookie_files:
            for idx, cookie_file in enumerate(valid_cookie_files, 1):
                try:
                    LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt B (Cookie #{idx} - {os.path.basename(cookie_file)}): yt-dlp video for {video_id}")
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
                    LOGGER(__name__).warning(f"[YT-AUTH] Video cookie #{idx} download failed ({err_type}) for {video_id}: {err_msg}")

        # Attempt C: yt-dlp video without cookies
        try:
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Attempt C: yt-dlp video (no cookies) for {video_id}")
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
            LOGGER(__name__).error(f"[YT-DOWNLOAD] yt-dlp video download (no cookies) failed for {video_id}: {e}")

        LOGGER(__name__).critical(f"[YT-DOWNLOAD] All video download fallbacks failed for video_id: {video_id}")
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

        # Primary Multi-Result Search: VideosSearch
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

        # Fallback 2: oEmbed details
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

        # Multi-result search via VideosSearch if it's a search term
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

        # Fallback 2: oEmbed details
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
