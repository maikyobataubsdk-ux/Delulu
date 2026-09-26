import os
import re
import difflib
import aiohttp
from typing import Optional, Tuple, Dict, Any, List
import config
from SONALI_MUSIC import LOGGER

DOWNLOAD_DIR = os.path.abspath("downloads")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

RAW_SAAVN_ENDPOINTS = [
    getattr(config, "SAAVN_API_URL", None),
    getattr(config, "JIOSAAVN_API_URL", None),
    "https://jiosaavn-a.kvinit6421.workers.dev/api/search/songs",
    "https://saavn.dev/api/search/songs",
    "https://jiosaavn-api-private-us.vercel.app/search/songs",
    "https://saavn.me/search/songs",
]

SAAVN_API_ENDPOINTS = []
for ep in RAW_SAAVN_ENDPOINTS:
    if ep and ep not in SAAVN_API_ENDPOINTS:
        SAAVN_API_ENDPOINTS.append(ep)


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


def generate_fallback_queries(raw_query: str) -> List[str]:
    """
    Generates a list of progressively simpler search queries from a raw query/title
    to maximize match rate on JioSaavn API.
    """
    if not raw_query:
        return []

    queries = []
    c_full = clean_song_title(raw_query)
    if c_full:
        queries.append(c_full)

    # Candidate 2: Main title before delimiters (|, -, :, /, \)
    delimiters_split = re.split(r"[\|\-:\/\\\\]", raw_query)
    if len(delimiters_split) > 1:
        c_part = clean_song_title(delimiters_split[0])
        if c_part and c_part not in queries:
            queries.append(c_part)

    # Candidate 3: First 3-4 key words of cleaned title
    if c_full:
        words = c_full.split()
        if len(words) > 3:
            c_short = " ".join(words[:4])
            if c_short not in queries:
                queries.append(c_short)
        if len(words) > 2:
            c_shorter = " ".join(words[:2])
            if c_shorter not in queries and len(c_shorter) >= 3:
                queries.append(c_shorter)

    if raw_query and raw_query not in queries:
        queries.append(raw_query)

    return queries


def calculate_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


class JioSaavnAPI:
    """Helper API class for JioSaavn audio search and direct stream downloading."""

    @staticmethod
    async def search_song(
        query: str,
        target_title: Optional[str] = None,
        target_artist: Optional[str] = None,
        target_duration: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        search_candidates = generate_fallback_queries(query)
        if not search_candidates:
            return None

        # Clean target title by extracting main part before hyphens/pipes/colons
        raw_target = target_title or query
        target_main_part = re.split(r"[\|\-:\/\\\\]", raw_target)[0]
        target_title_clean = clean_song_title(target_main_part) or clean_song_title(raw_target)

        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            for clean_q in search_candidates:
                LOGGER(__name__).info(f"[JIOSAAVN] Searching JioSaavn for query candidate: '{clean_q}' (Original: '{query}')")
                for endpoint in SAAVN_API_ENDPOINTS:
                    try:
                        params = {"query": clean_q, "limit": 10}
                        async with session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                results = (
                                    data.get("data", {}).get("results", [])
                                    if isinstance(data.get("data"), dict)
                                    else data.get("data", [])
                                )
                                if not results and isinstance(data, list):
                                    results = data

                                if not results or not isinstance(results, list):
                                    continue

                                candidates = []

                                for song in results:
                                    if not isinstance(song, dict):
                                        continue
                                    title = song.get("name") or song.get("title") or song.get("song") or ""
                                    song_id = song.get("id") or song.get("song_id") or "saavn_track"
                                    duration = song.get("duration") or song.get("duration_sec") or 0
                                    try:
                                        duration_sec = int(duration)
                                    except Exception:
                                        duration_sec = 0

                                    primary_artists = ""
                                    if isinstance(song.get("primaryArtists"), str):
                                        primary_artists = song.get("primaryArtists")
                                    elif isinstance(song.get("artists"), dict):
                                        primary_list = song.get("artists", {}).get("primary", [])
                                        if isinstance(primary_list, list):
                                            names = [a.get("name") for a in primary_list if isinstance(a, dict) and a.get("name")]
                                            primary_artists = ", ".join(names)
                                    elif isinstance(song.get("artists"), str):
                                        primary_artists = song.get("artists")

                                    # Download URLs extraction
                                    download_urls = (
                                        song.get("downloadUrl")
                                        or song.get("download_url")
                                        or song.get("media_url")
                                        or song.get("media_urls")
                                        or song.get("vlink")
                                        or song.get("url")
                                        or []
                                    )
                                    stream_url = None
                                    if isinstance(download_urls, list) and download_urls:
                                        quality_map = {}
                                        for item in download_urls:
                                            if isinstance(item, dict):
                                                q = str(item.get("quality", "")).lower()
                                                u = item.get("url") or item.get("link")
                                                if u:
                                                    quality_map[q] = u
                                            elif isinstance(item, str) and item.startswith("http"):
                                                stream_url = item
                                        if not stream_url and quality_map:
                                            for q_key in ["320kbps", "160kbps", "96kbps", "48kbps", "12kbps"]:
                                                if q_key in quality_map:
                                                    stream_url = quality_map[q_key]
                                                    break
                                            if not stream_url:
                                                stream_url = list(quality_map.values())[-1]
                                        elif not stream_url and isinstance(download_urls[-1], dict):
                                            stream_url = download_urls[-1].get("url") or download_urls[-1].get("link")
                                        elif not stream_url and isinstance(download_urls[-1], str):
                                            stream_url = download_urls[-1]
                                    elif isinstance(download_urls, dict):
                                        stream_url = download_urls.get("320kbps") or download_urls.get("160kbps") or download_urls.get("url") or download_urls.get("link")
                                    elif isinstance(download_urls, str) and download_urls.startswith("http"):
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

                                # Sort candidates by title similarity, artist similarity, and duration difference
                                def score_candidate(c):
                                    dur_penalty = 0.0
                                    if target_duration and target_duration > 0:
                                        if c["dur_diff"] > 15:
                                            dur_penalty = (c["dur_diff"] - 15) * 0.05
                                    return (c["title_sim"] * 0.6) + (c["artist_sim"] * 0.4) - dur_penalty

                                candidates.sort(key=score_candidate, reverse=True)
                                best = candidates[0]

                                song = best["song"]
                                title = best["title"]
                                song_id = best["song_id"]
                                duration_sec = best["duration_sec"]
                                stream_url = best["stream_url"]
                                duration_min = f"{duration_sec // 60}:{duration_sec % 60:02d}" if duration_sec else "3:30"

                                image_list = song.get("image") or song.get("images") or []
                                thumb = "https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg"
                                if isinstance(image_list, list) and image_list:
                                    quality_map = {}
                                    for item in image_list:
                                        if isinstance(item, dict):
                                            q = str(item.get("quality", "")).lower()
                                            u = item.get("url") or item.get("link")
                                            if u:
                                                quality_map[q] = u
                                        elif isinstance(item, str) and item.startswith("http"):
                                            thumb = item
                                    if quality_map:
                                        for q_key in ["500x500", "150x150", "50x50"]:
                                            if q_key in quality_map:
                                                thumb = quality_map[q_key]
                                                break
                                        if thumb == "https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg":
                                            thumb = list(quality_map.values())[-1]
                                    elif isinstance(image_list[-1], dict):
                                        thumb = image_list[-1].get("url") or image_list[-1].get("link") or thumb
                                    elif isinstance(image_list[-1], str):
                                        thumb = image_list[-1]
                                elif isinstance(image_list, str) and image_list.startswith("http"):
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
