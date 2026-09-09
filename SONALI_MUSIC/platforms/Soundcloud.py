import os
from os import path
from yt_dlp import YoutubeDL
from SONALI_MUSIC.utils.formatters import seconds_to_min
from SONALI_MUSIC.utils.youtube_utils import get_cookie_file, analyze_cookies


class SoundAPI:
    def __init__(self):
        self.opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "format": "best",
            "retries": 5,
            "socket_timeout": 20,
            "nooverwrites": False,
            "continuedl": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
        }
        cookie_analysis = analyze_cookies()
        if cookie_analysis["status"] == "VALID" and cookie_analysis["cookie_path"]:
            self.opts["cookiefile"] = os.path.abspath(cookie_analysis["cookie_path"])

    async def valid(self, link: str):
        if "soundcloud" in link:
            return True
        else:
            return False

    async def download(self, url):
        d = YoutubeDL(self.opts)
        try:
            info = d.extract_info(url)
        except:
            return False
        xyz = path.join("downloads", f"{info['id']}.{info['ext']}")
        duration_min = seconds_to_min(info["duration"])
        track_details = {
            "title": info["title"],
            "duration_sec": info["duration"],
            "duration_min": duration_min,
            "uploader": info["uploader"],
            "filepath": xyz,
        }
        return track_details, xyz
