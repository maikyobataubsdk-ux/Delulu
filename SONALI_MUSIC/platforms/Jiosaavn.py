import os
import re
import difflib
import aiohttp
from typing import Optional, Tuple, Dict, Any, List
from SONALI_MUSIC import LOGGER

DOWNLOAD_DIR = os.path.abspath("downloads")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

SAAVN_API_ENDPOINTS = [
    "https://saavn.dev/api/search/songs",
    "https://jiosaavn-api-private-us.vercel.app/search/songs",
    "https://saavn.me/search/songs",
]


def clean_song_title(title: str) -> str:
    """
    Cleans song title by removing common video tags like (Official Video),
    [Lyrics], 4K, HD, Full Video, pipes, year tags, etc.
    """
    if not title:
        return ""
    # Remove contents inside brackets/parentheses/braces
    cleaned = re.sub(r"[\(\[\{].*?[\)\]\}]", "", title)
    # Remove specific noise words/tags case-insensitively
    noise_pattern = r"(?i)\b(official lyric video|official video|lyric video|official|lyrical|lyrics|4k|hd|full video|audio|remix|feat|ft|video|vevo|teaser|trailer|love song|song|music video|full song|1080p|720p|\d{4})\b"
    cleaned = re.sub(noise_pattern, " ", cleaned)
    # Replace pipe, slash, backslash, hyphen or standalone 'I' delimiter with space
    cleaned = re.sub(r"[|/\\–—]", " ", cleaned)
    cleaned = re.sub(r"\s+I\s+", " ", cleaned)
    # Normalize extra whitespaces
    return " ".join(cleaned.split()).strip()


def calculate_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


class JioSaavnAPI:
    """Helper API class for JioSaavn audio search and direct stream downloading."""

    @staticmethod
    async def search_song(query: str, target_title: Optional[str] = None, target_artist: Optional[str] = None, target_duration: Optional[int] = None) -> Optional[Dict[str, Any]]:
        clean_q = clean_song_title(query) or query
        if not clean_q:
            return None
        LOGGER(__name__).info(f"[JIOSAAVN] Searching JioSaavn for clean query: '{clean_q}' (Original: '{query}')")
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            for endpoint in SAAVN_API_ENDPOINTS:
                try:
                    params = {"query": clean_q, "limit": 5}
                    async with session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("data", {}).get("results", []) if isinstance(data.get("data"), dict) else data.get("data", [])
                            if not results and isinstance(data, list):
                                results = data

                            if not results:
                                continue

                            candidates = []
                            target_title_clean = clean_song_title(target_title or query)

                            for song in results:
                                title = song.get("name") or song.get("title") or ""
                                song_id = song.get("id", "saavn_track")
                                duration = song.get("duration") or 0
                                try:
                                    duration_sec = int(duration)
                                except Exception:
                                    duration_sec = 0

                                primary_artists = ""
                                if isinstance(song.get("primaryArtists"), str):
                                    primary_artists = song.get("primaryArtists")
                                elif isinstance(song.get("artists"), dict):
                                    primary_artists = song.get("artists", {}).get("primary", [{}])[0].get("name", "")

                                # Download URLs
                                download_urls = song.get("downloadUrl") or []
                                stream_url = None
                                if isinstance(download_urls, list) and download_urls:
                                    stream_url = download_urls[-1].get("url") or download_urls[-1].get("link")
                                elif isinstance(download_urls, str):
                                    stream_url = download_urls

                                if not stream_url:
                                    continue

                                # Calculate similarity scores
                                clean_candidate_title = clean_song_title(title)
                                title_sim = calculate_similarity(target_title_clean, clean_candidate_title)

                                artist_sim = 1.0
                                if target_artist and primary_artists:
                                    artist_sim = calculate_similarity(target_artist, primary_artists)

                                dur_diff = 0
                                if target_duration and target_duration > 0 and duration_sec > 0:
                                    dur_diff = abs(target_duration - duration_sec)
                                else:
                                    dur_diff = 0

                                candidates.append({
                                    "song": song,
                                    "title": title,
                                    "song_id": song_id,
                                    "duration_sec": duration_sec,
                                    "stream_url": stream_url,
                                    "title_sim": title_sim,
                                    "artist_sim": artist_sim,
                                    "dur_diff": dur_diff,
                                })

                            if not candidates:
                                continue

                            # Sort candidates by title similarity, artist similarity, and duration difference (< 15 sec preference)
                            def score_candidate(c):
                                dur_penalty = 0.0
                                if target_duration and target_duration > 0:
                                    if c["dur_diff"] > 15:
                                        dur_penalty = (c["dur_diff"] - 15) * 0.05
                                return (c["title_sim"] * 0.6) + (c["artist_sim"] * 0.4) - dur_penalty

                            candidates.sort(key=score_candidate, reverse=True)
                            best = candidates[0]

                            # Accept best candidate
                            song = best["song"]
                            title = best["title"]
                            song_id = best["song_id"]
                            duration_sec = best["duration_sec"]
                            stream_url = best["stream_url"]
                            duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "3:30"

                            image_list = song.get("image") or []
                            thumb = "https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg"
                            if isinstance(image_list, list) and image_list:
                                thumb = image_list[-1].get("url") or image_list[-1].get("link") or thumb
                            elif isinstance(image_list, str):
                                thumb = image_list

                            LOGGER(__name__).info(f"[JIOSAAVN] Matched track on JioSaavn: {title} ({song_id}) [TitleSim: {best['title_sim']:.2f}, DurDiff: {best['dur_diff']}s]")
                            return {
                                "title": title,
                                "id": song_id,
                                "duration_min": duration_min,
                                "duration_sec": duration_sec,
                                "thumb": thumb,
                                "stream_url": stream_url,
                            }
                except Exception as e:
                    LOGGER(__name__).debug(f"[JIOSAAVN] Search endpoint {endpoint} failed: {e}")

        return None

    @classmethod
    async def download_song_by_query(
        cls,
        query: str,
        dest_filename: str,
        target_title: Optional[str] = None,
        target_artist: Optional[str] = None,
        target_duration: Optional[int] = None,
    ) -> Optional[str]:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        dest_path = os.path.join(DOWNLOAD_DIR, dest_filename)

        song_info = await cls.search_song(
            query=query,
            target_title=target_title,
            target_artist=target_artist,
            target_duration=target_duration,
        )
        if not song_info or not song_info.get("stream_url"):
            return None

        stream_url = song_info["stream_url"]
        try:
            LOGGER(__name__).info(f"[JIOSAAVN] Downloading track audio from JioSaavn stream: {stream_url}")
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024:
                            LOGGER(__name__).info(f"[JIOSAAVN] Download successful: {dest_path}")
                            return dest_path
        except Exception as e:
            LOGGER(__name__).error(f"[JIOSAAVN] Failed to download JioSaavn audio: {e}")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception:
                    pass

        return None


JioSaavn = JioSaavnAPI()
