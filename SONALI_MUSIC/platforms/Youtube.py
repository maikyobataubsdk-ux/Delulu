import asyncio
import os
import re
from typing import Union
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
import aiohttp

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

DOWNLOAD_DIR = "downloads"


def get_cookie_file():
    for path in ["cookies/cookies.txt", "SONALI_MUSIC/assets/cookies.txt", "assets/cookies.txt"]:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    return None


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


async def download_song(link: str) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    # Primary: Shruti API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": video_id, "type": "audio", "api_key": API_KEY},
                timeout=aiohttp.ClientTimeout(total=300)
            ) as resp:
                if resp.status == 200:
                    with open(file_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(131072):
                            f.write(chunk)
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        return file_path
    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    yt_link = f"https://www.youtube.com/watch?v={video_id}" if not link.startswith("http") else link

    # Fallback 1: yt-dlp with cookies (if present)
    cookie_file = get_cookie_file()
    if cookie_file:
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "cookiefile": cookie_file,
                "js_runtimes": {"node": {}},
                "remote_components": ["ejs:github"],
            }
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([yt_link])
            )
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path
        except Exception:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    # Fallback 2: yt-dlp WITHOUT cookies (in case cookies are rate limited/blocked)
    try:
        ydl_opts_nocookie = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts_nocookie).download([yt_link])
        )
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    return None


async def download_video(link: str) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    # Primary: Shruti API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": video_id, "type": "video", "api_key": API_KEY},
                timeout=aiohttp.ClientTimeout(total=600)
            ) as resp:
                if resp.status == 200:
                    with open(file_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(131072):
                            f.write(chunk)
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        return file_path
    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    yt_link = f"https://www.youtube.com/watch?v={video_id}" if not link.startswith("http") else link

    # Fallback 1: yt-dlp with cookies
    cookie_file = get_cookie_file()
    if cookie_file:
        try:
            ydl_opts = {
                "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": file_path,
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "cookiefile": cookie_file,
                "js_runtimes": {"node": {}},
                "remote_components": ["ejs:github"],
            }
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([yt_link])
            )
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path
        except Exception:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    # Fallback 2: yt-dlp WITHOUT cookies
    try:
        ydl_opts_nocookie = {
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": file_path,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts_nocookie).download([yt_link])
        )
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def _oembed_details(self, vidid: str):
        try:
            url = f"{self.base}{vidid}"
            oembed_url = f"{self.status}{url}&format=json"
            async with aiohttp.ClientSession() as session:
                async with session.get(oembed_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        title = data.get("title", "Unknown Title")
                        thumbnail = data.get("thumbnail_url", f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg")
                        return title, thumbnail
        except Exception:
            pass
        return "Unknown Title", f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"

    async def exists(self, link: str, videoid: Union[bool, str] = None):
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

        vidid = link.split("v=")[-1].split("&")[0] if "v=" in link else link

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
            except Exception:
                pass

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
        except Exception:
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        vidid = link.split("v=")[-1].split("&")[0] if "v=" in link else link

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
            except Exception:
                pass

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
        ytdl_opts = {
            "quiet": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
        }
        cookie_file = get_cookie_file()
        if cookie_file:
            ytdl_opts["cookiefile"] = cookie_file
        formats_available = []
        try:
            ydl = yt_dlp.YoutubeDL(ytdl_opts)
            with ydl:
                r = ydl.extract_info(link, download=False)
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
        except Exception:
            pass
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
            except Exception:
                pass

        vidid = link.split("v=")[-1].split("&")[0] if "v=" in link else link
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
                    raise Exception("Download failed")
                else:
                    return None, False
            if is_song_downloader:
                return downloaded_file
            else:
                return downloaded_file, True
        except Exception as e:
            if is_song_downloader:
                raise e
            else:
                return None, False


YouTube = YouTubeAPI()
