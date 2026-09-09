import asyncio
import os
import re
import traceback
from typing import Union, Optional, Tuple, Dict, Any
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
import aiohttp
from SONALI_MUSIC import LOGGER
from SONALI_MUSIC.utils.youtube_utils import get_cookie_file, analyze_cookies, classify_ytdl_error

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


def get_ytdl_base_opts(cookie_file: Optional[str] = None) -> Dict[str, Any]:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "ignoreerrors": True,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb", "web"]}},
    }
    if cookie_file:
        opts["cookiefile"] = os.path.abspath(cookie_file)
    return opts


async def download_song(link: str) -> Optional[str]:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3:
        LOGGER(__name__).warning(f"Invalid video_id extracted from link: {link}")
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    existing_file = find_downloaded_file(video_id, is_video=False)
    if existing_file:
        return existing_file

    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    # Attempt 1: Shruti API
    try:
        LOGGER(__name__).info(f"Attempting download via Shruti API for video_id: {video_id}")
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
                        LOGGER(__name__).info(f"Shruti API download successful for {video_id}")
                        return file_path
                    else:
                        if os.path.exists(file_path):
                            os.remove(file_path)
    except Exception as e:
        LOGGER(__name__).error(f"Shruti API download error for {video_id}: {e}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    yt_link = f"https://www.youtube.com/watch?v={video_id}"
    cookie_analysis = analyze_cookies()
    cookie_file = cookie_analysis["cookie_path"] if cookie_analysis["status"] == "VALID" else None
    loop = asyncio.get_event_loop()

    # Attempt 2: yt-dlp bestaudio with FFmpeg conversion (with cookies if valid)
    if cookie_file:
        try:
            LOGGER(__name__).info(f"Attempting yt-dlp bestaudio MP3 with cookies for {video_id}")
            ydl_opts = get_ytdl_base_opts(cookie_file)
            ydl_opts.update({
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            })
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([yt_link])
            )
            downloaded = find_downloaded_file(video_id, is_video=False)
            if downloaded:
                return downloaded
        except Exception as e:
            err_type, err_msg = classify_ytdl_error(e)
            if err_type == "AUTH_REQUIRED":
                LOGGER(__name__).error(f"yt-dlp cookie authentication failed for {video_id}: {err_msg}")
            else:
                LOGGER(__name__).error(f"yt-dlp bestaudio MP3 failed for {video_id}: {e}")

    # Attempt 3: yt-dlp without cookies
    try:
        LOGGER(__name__).info(f"Attempting yt-dlp bestaudio MP3 without cookies for {video_id}")
        ydl_opts_nocookie = get_ytdl_base_opts(cookie_file=None)
        ydl_opts_nocookie.update({
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        })
        await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts_nocookie).download([yt_link])
        )
        downloaded = find_downloaded_file(video_id, is_video=False)
        if downloaded:
            return downloaded
    except Exception as e:
        LOGGER(__name__).error(f"yt-dlp bestaudio MP3 (no cookies) failed for {video_id}: {e}")

    # Attempt 4: yt-dlp raw bestaudio/best without postprocessing
    try:
        LOGGER(__name__).info(f"Attempting yt-dlp raw audio for {video_id}")
        ydl_opts_raw = get_ytdl_base_opts(cookie_file=None)
        ydl_opts_raw.update({
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
        })
        await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts_raw).download([yt_link])
        )
        downloaded = find_downloaded_file(video_id, is_video=False)
        if downloaded:
            return downloaded
    except Exception as e:
        LOGGER(__name__).error(f"yt-dlp raw audio failed for {video_id}: {e}")

    # Attempt 5: Progressive format fallback
    try:
        LOGGER(__name__).info(f"Attempting yt-dlp progressive fallback for {video_id}")
        ydl_opts_prog = get_ytdl_base_opts(cookie_file=None)
        ydl_opts_prog.update({
            "format": "best[ext=mp4]/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
        })
        await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts_prog).download([yt_link])
        )
        downloaded = find_downloaded_file(video_id, is_video=False)
        if downloaded:
            return downloaded
    except Exception as e:
        LOGGER(__name__).error(f"yt-dlp progressive fallback failed for {video_id}: {e}")

    LOGGER(__name__).critical(f"All song download fallbacks failed for video_id: {video_id}")
    return None


async def download_video(link: str) -> Optional[str]:
    video_id = extract_video_id(link)
    if not video_id or len(video_id) < 3:
        LOGGER(__name__).warning(f"Invalid video_id extracted from link: {link}")
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    existing_file = find_downloaded_file(video_id, is_video=True)
    if existing_file:
        return existing_file

    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    # Attempt 1: Shruti API
    try:
        LOGGER(__name__).info(f"Attempting video download via Shruti API for video_id: {video_id}")
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
                        LOGGER(__name__).info(f"Shruti API video download successful for {video_id}")
                        return file_path
                    else:
                        if os.path.exists(file_path):
                            os.remove(file_path)
    except Exception as e:
        LOGGER(__name__).error(f"Shruti API video download error for {video_id}: {e}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    yt_link = f"https://www.youtube.com/watch?v={video_id}"
    cookie_analysis = analyze_cookies()
    cookie_file = cookie_analysis["cookie_path"] if cookie_analysis["status"] == "VALID" else None
    loop = asyncio.get_event_loop()

    # Attempt 2: yt-dlp video format selection (with cookies if valid)
    if cookie_file:
        try:
            LOGGER(__name__).info(f"Attempting yt-dlp video download with cookies for {video_id}")
            ydl_opts = get_ytdl_base_opts(cookie_file)
            ydl_opts.update({
                "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
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
            if err_type == "AUTH_REQUIRED":
                LOGGER(__name__).error(f"yt-dlp video cookie authentication failed for {video_id}: {err_msg}")
            else:
                LOGGER(__name__).error(f"yt-dlp video download failed for {video_id}: {e}")

    # Attempt 3: yt-dlp video format selection (no cookies)
    try:
        LOGGER(__name__).info(f"Attempting yt-dlp video download without cookies for {video_id}")
        ydl_opts_nocookie = get_ytdl_base_opts(cookie_file=None)
        ydl_opts_nocookie.update({
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
        })
        await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts_nocookie).download([yt_link])
        )
        downloaded = find_downloaded_file(video_id, is_video=True)
        if downloaded:
            return downloaded
    except Exception as e:
        LOGGER(__name__).error(f"yt-dlp video download (no cookies) failed for {video_id}: {e}")

    LOGGER(__name__).critical(f"All video download fallbacks failed for video_id: {video_id}")
    return None


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
            LOGGER(__name__).error(f"oEmbed fetch error for {vidid}: {e}")
        return "Unknown Title", f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"

    async def _ytdl_extract_track_info(self, query_or_url: str) -> Optional[Tuple[Dict[str, Any], str]]:
        loop = asyncio.get_event_loop()
        cookie_analysis = analyze_cookies()
        cookie_file = cookie_analysis["cookie_path"] if cookie_analysis["status"] == "VALID" else None
        ydl_opts = get_ytdl_base_opts(cookie_file)
        target = query_or_url if ("youtube.com" in query_or_url or "youtu.be" in query_or_url) else f"ytsearch1:{query_or_url}"

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(target, download=False)

        try:
            info = await loop.run_in_executor(None, _extract)
            if info:
                if "entries" in info and info["entries"]:
                    entry = info["entries"][0]
                else:
                    entry = info
                if entry:
                    v_id = entry.get("id")
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
                    return track_details, v_id
        except Exception as e:
            err_type, err_msg = classify_ytdl_error(e)
            if err_type == "AUTH_REQUIRED":
                LOGGER(__name__).error(f"yt-dlp extract_info authentication required: {err_msg}")
            else:
                LOGGER(__name__).error(f"yt-dlp extract_info fallback error for {query_or_url}: {e}")
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

        if VideosSearch is not None:
            try:
                results = VideosSearch(link, limit=1)
                res = await results.next()
                if res.get("result"):
                    result = res["result"][0]
                    title = result["title"]
                    duration_min = result["duration"]
                    thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                    v_id = result["id"]
                    duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
                    return title, duration_min, duration_sec, thumbnail, v_id
            except Exception as e:
                LOGGER(__name__).error(f"VideosSearch details error: {e}")

        # Fallback 1: yt-dlp metadata
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
            LOGGER(__name__).error(f"YouTube.video error: {e}\n{traceback.format_exc()}")
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
            LOGGER(__name__).error(f"YouTube.playlist error: {e}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        vidid = extract_video_id(link)

        # Primary Search: VideosSearch
        if VideosSearch is not None:
            try:
                results = VideosSearch(link, limit=1)
                res = await results.next()
                if res.get("result"):
                    result = res["result"][0]
                    title = result["title"]
                    duration_min = result["duration"]
                    v_id = result["id"]
                    yturl = result["link"]
                    thumbnail = result["thumbnails"][0]["url"].split("?")[0]
                    track_details = {
                        "title": title,
                        "link": yturl,
                        "vidid": v_id,
                        "duration_min": duration_min,
                        "thumb": thumbnail,
                    }
                    return track_details, v_id
            except Exception as e:
                LOGGER(__name__).error(f"YouTube.track VideosSearch error for '{link}': {e}")

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

        cookie_analysis = analyze_cookies()
        cookie_file = cookie_analysis["cookie_path"] if cookie_analysis["status"] == "VALID" else None
        ytdl_opts = get_ytdl_base_opts(cookie_file)
        formats_available = []
        try:
            loop = asyncio.get_event_loop()
            def _extract_formats():
                with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                    return ydl.extract_info(link, download=False)
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
        except Exception as e:
            LOGGER(__name__).error(f"YouTube.formats error: {e}")
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
                LOGGER(__name__).error(f"YouTube.slider error: {e}")

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
            LOGGER(__name__).error(f"YouTube.download error: {e}\n{traceback.format_exc()}")
            if is_song_downloader:
                raise e
            else:
                return None, False


YouTube = YouTubeAPI()
