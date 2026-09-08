import os
from os import path
import yt_dlp
from yt_dlp.utils import DownloadError


def get_cookie_file():
    for p in ["cookies/cookies.txt", "SONALI_MUSIC/assets/cookies.txt", "assets/cookies.txt"]:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


ytdl_init_opts = {
    "outtmpl": "downloads/%(id)s.%(ext)s",
    "format": "bestaudio/best",
    "geo_bypass": True,
    "nocheckcertificate": True,
    "js_runtimes": {"node": {}},
    "remote_components": ["ejs:github"],
    "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb", "web"]}},
}
_cookie_file = get_cookie_file()
if _cookie_file:
    ytdl_init_opts["cookiefile"] = _cookie_file

ytdl = yt_dlp.YoutubeDL(ytdl_init_opts)


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
    ydl_optssx = {
        'format': 'bestaudio/best',
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "geo_bypass": True,
        "nocheckcertificate": True,
        'quiet': True,
        'no_warnings': True,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb", "web"]}},
    }
    cookie_file = get_cookie_file()
    if cookie_file:
        ydl_optssx["cookiefile"] = cookie_file
    try:
        info = ytdl.extract_info(url, False)
    except Exception:
        opts_nocookie = dict(ytdl_init_opts)
        opts_nocookie.pop("cookiefile", None)
        ydl_optssx.pop("cookiefile", None)
        try:
            info = yt_dlp.YoutubeDL(opts_nocookie).extract_info(url, False)
        except Exception as e:
            print(f"ytdl extract_info error: {e}")
            return None
    try:
        x = yt_dlp.YoutubeDL(ydl_optssx)
        if my_hook:
            x.add_progress_hook(my_hook)
        dloader = x.download([url])
    except Exception as y_e:
        print(f"ytdl download error: {y_e}")
        vid_id = info.get("id") if info else None
        if vid_id:
            found = find_downloaded_file_by_id(vid_id)
            if found:
                return found
        return None

    vid_id = info.get("id") if info else None
    if vid_id:
        found = find_downloaded_file_by_id(vid_id)
        if found:
            return found

    xyz = path.join("downloads", f"{info['id']}.{info['ext']}") if info and 'id' in info and 'ext' in info else None
    return xyz
