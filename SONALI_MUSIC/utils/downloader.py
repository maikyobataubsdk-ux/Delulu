import os
from os import path
import yt_dlp
from yt_dlp.utils import DownloadError
from SONALI_MUSIC import LOGGER
from SONALI_MUSIC.utils.youtube_utils import get_cookie_file, analyze_cookies, classify_ytdl_error


def get_downloader_opts(cookie_file=None):
    opts = {
        "outtmpl": "downloads/%(id)s.%(ext)s",
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


def download(url: str, my_hook) -> str:
    os.makedirs("downloads", exist_ok=True)
    cookie_analysis = analyze_cookies()
    cookie_file = cookie_analysis["cookie_path"] if cookie_analysis["status"] == "VALID" else None
    ytdl_opts = get_downloader_opts(cookie_file)

    info = None
    try:
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        info = ydl.extract_info(url, False)
    except Exception as e:
        err_type, err_msg = classify_ytdl_error(e)
        LOGGER(__name__).error(f"Downloader initial extract_info error ({err_type}): {e}")
        if cookie_file:
            try:
                opts_nocookie = get_downloader_opts(cookie_file=None)
                info = yt_dlp.YoutubeDL(opts_nocookie).extract_info(url, False)
            except Exception as ex:
                LOGGER(__name__).error(f"Downloader extract_info without cookies error: {ex}")
                info = None

    vid_id = info.get("id") if info else None
    if vid_id:
        existing = find_downloaded_file_by_id(vid_id)
        if existing:
            return existing

    try:
        x_opts = dict(ytdl_opts)
        x = yt_dlp.YoutubeDL(x_opts)
        if my_hook:
            x.add_progress_hook(my_hook)
        x.download([url])
    except Exception as y_e:
        LOGGER(__name__).error(f"Downloader download error: {y_e}")
        if vid_id:
            found = find_downloaded_file_by_id(vid_id)
            if found:
                return found
        # Attempt retry without cookies
        if cookie_file:
            try:
                LOGGER(__name__).info("Retrying downloader without cookies...")
                nocookie_opts = get_downloader_opts(cookie_file=None)
                x_nc = yt_dlp.YoutubeDL(nocookie_opts)
                if my_hook:
                    x_nc.add_progress_hook(my_hook)
                x_nc.download([url])
            except Exception as nc_e:
                LOGGER(__name__).error(f"Downloader download without cookies error: {nc_e}")

    if vid_id:
        found = find_downloaded_file_by_id(vid_id)
        if found:
            return found

    if info and 'id' in info and 'ext' in info:
        xyz = path.join("downloads", f"{info['id']}.{info['ext']}")
        if os.path.exists(xyz) and os.path.getsize(xyz) > 1024:
            return xyz

    return None
