import os
from os import path
import yt_dlp
from SONALI_MUSIC import LOGGER
from SONALI_MUSIC.utils.youtube_utils import get_valid_cookie_files, classify_ytdl_error, get_ffmpeg_path


def get_downloader_opts(cookie_file=None):
    opts = {
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "format": "bestaudio/bestvideo+bestaudio/best",
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
    ff_path = get_ffmpeg_path()
    if ff_path:
        opts["ffmpeg_location"] = ff_path
    if cookie_file:
        opts["cookiefile"] = os.path.abspath(cookie_file)
    return opts


def find_downloaded_file_by_id(vid_id: str) -> str:
    downloads_dir = "downloads"
    if not os.path.exists(downloads_dir):
        return None
    for f in os.listdir(downloads_dir):
        if f.startswith(f"{vid_id}."):
            fp = path.join(downloads_dir, f)
            if os.path.exists(fp) and os.path.getsize(fp) > 1024:
                return fp
    return None


def download(url: str, my_hook=None) -> str:
    os.makedirs("downloads", exist_ok=True)

    valid_cookie_files = get_valid_cookie_files()
    cookie_candidates = valid_cookie_files + [None]

    info = None
    for idx, cookie_file in enumerate(cookie_candidates, 1):
        ytdl_opts = get_downloader_opts(cookie_file)
        c_name = os.path.basename(cookie_file) if cookie_file else "no-cookies"
        try:
            ydl = yt_dlp.YoutubeDL(ytdl_opts)
            info = ydl.extract_info(url, False)
            if info:
                LOGGER(__name__).info(f"[YT-DOWNLOAD] Downloader extract_info successful with candidate #{idx} ({c_name})")
                break
        except Exception as e:
            err_type, err_msg = classify_ytdl_error(e)
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Downloader extract_info failed ({err_type}) with candidate #{idx} ({c_name}): {err_msg}")

    vid_id = info.get("id") if info else None
    if vid_id:
        existing = find_downloaded_file_by_id(vid_id)
        if existing:
            return existing

    for idx, cookie_file in enumerate(cookie_candidates, 1):
        c_name = os.path.basename(cookie_file) if cookie_file else "no-cookies"
        try:
            x_opts = get_downloader_opts(cookie_file)
            x = yt_dlp.YoutubeDL(x_opts)
            if my_hook:
                x.add_progress_hook(my_hook)
            x.download([url])
            if vid_id:
                found = find_downloaded_file_by_id(vid_id)
                if found:
                    LOGGER(__name__).info(f"[YT-DOWNLOAD] Downloader download successful with candidate #{idx} ({c_name})")
                    return found
        except Exception as y_e:
            LOGGER(__name__).error(f"[YT-DOWNLOAD] Downloader download error with candidate #{idx} ({c_name}): {y_e}")
            if vid_id:
                found = find_downloaded_file_by_id(vid_id)
                if found:
                    return found

    if vid_id:
        found = find_downloaded_file_by_id(vid_id)
        if found:
            return found

    if info and 'id' in info and 'ext' in info:
        xyz = path.join("downloads", f"{info['id']}.{info['ext']}")
        if os.path.exists(xyz) and os.path.getsize(xyz) > 1024:
            return xyz

    return None
