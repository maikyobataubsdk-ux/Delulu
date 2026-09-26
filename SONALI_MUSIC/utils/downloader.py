import os
import asyncio
import concurrent.futures
from os import path
import yt_dlp
from SONALI_MUSIC import LOGGER
from SONALI_MUSIC.platforms.Youtube import YouTubeExtractor, extract_video_id, is_valid_media_file
from SONALI_MUSIC.utils.youtube_utils import (
    get_valid_cookie_files,
    get_next_cookie_file,
    classify_ytdl_error,
    get_ytdl_base_opts,
    mark_cookie_unusable,
    AudioCache,
)


def find_downloaded_file_by_id(vid_id: str) -> str:
    downloads_dir = "downloads"
    if not os.path.exists(downloads_dir):
        return None
    for f in os.listdir(downloads_dir):
        if f.startswith(f"{vid_id}."):
            fp = path.join(downloads_dir, f)
            if is_valid_media_file(fp):
                return fp
    return None


def download(url: str, my_hook=None) -> str:
    os.makedirs("downloads", exist_ok=True)

    # Attempt 1: Centralized API System via YouTubeExtractor
    try:
        vid_id = extract_video_id(url)
        if vid_id:
            cached_item = AudioCache.get(vid_id)
            if cached_item and cached_item.get("local_path") and is_valid_media_file(cached_item["local_path"]):
                return cached_item["local_path"]
            existing = find_downloaded_file_by_id(vid_id)
            if existing:
                return existing

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(asyncio.run, YouTubeExtractor.download_song(url)).result()
        else:
            res = loop.run_until_complete(YouTubeExtractor.download_song(url))

        if res and is_valid_media_file(res):
            LOGGER(__name__).info(f"[YT-DOWNLOAD] Downloader helper retrieved media using API system: {res}")
            return res
    except Exception as e:
        LOGGER(__name__).warning(f"[YT-DOWNLOAD] Downloader helper API attempt encountered error: {e}")

    # Attempt 2: Local yt-dlp Multi-Cookie and No-Cookie Sequential Fallback
    valid_cookie_files = get_valid_cookie_files()
    next_cookie = get_next_cookie_file()
    if next_cookie and next_cookie in valid_cookie_files:
        valid_cookie_files.remove(next_cookie)
        valid_cookie_files.insert(0, next_cookie)
    cookie_candidates = valid_cookie_files + [None]

    info = None
    for idx, cookie_file in enumerate(cookie_candidates, 1):
        ytdl_opts = get_ytdl_base_opts(cookie_file=cookie_file)
        c_name = os.path.basename(cookie_file) if cookie_file else "no-cookies"
        try:
            ydl = yt_dlp.YoutubeDL(ytdl_opts)
            info = ydl.extract_info(url, False)
            if info:
                LOGGER(__name__).info(f"[YT-DOWNLOAD] Downloader extract_info successful with candidate #{idx} ({c_name})")
                break
        except Exception as e:
            err_type, err_msg = classify_ytdl_error(e)
            if cookie_file and err_type in ("BOT_CHECK", "AUTH_REQUIRED"):
                mark_cookie_unusable(cookie_file)
            LOGGER(__name__).warning(f"[YT-DOWNLOAD] Downloader extract_info failed ({err_type}) with candidate #{idx} ({c_name}): {err_msg}")

    vid_id = info.get("id") if info else None
    if vid_id:
        existing = find_downloaded_file_by_id(vid_id)
        if existing:
            return existing

    for idx, cookie_file in enumerate(cookie_candidates, 1):
        c_name = os.path.basename(cookie_file) if cookie_file else "no-cookies"
        try:
            x_opts = get_ytdl_base_opts(cookie_file=cookie_file)
            x_opts["outtmpl"] = "downloads/%(id)s.%(ext)s"
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
            err_type, _ = classify_ytdl_error(y_e)
            if cookie_file and err_type in ("BOT_CHECK", "AUTH_REQUIRED"):
                mark_cookie_unusable(cookie_file)
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
        if is_valid_media_file(xyz):
            return xyz

    return None
