import os
import shutil
import time
import json
import subprocess
import socket
import urllib.parse
from typing import Dict, Any, Optional, Tuple, List, Union, Set
import yt_dlp
import config
from SONALI_MUSIC import LOGGER

REQUIRED_AUTH_COOKIES = {"SID", "SSID", "SAPISID", "__Secure-1PSID", "__Secure-3PSID"}
VISITOR_COOKIE_NAMES = {"PREF", "SOCS", "YSC", "VISITOR_INFO1_LIVE", "VISITOR_PRIVACY_METADATA", "__Secure-ROLLOUT_TOKEN", "GPS"}

CACHE_FILE_PATH = os.path.abspath(os.path.join("downloads", "audio_cache.json"))


class CircuitBreaker:
    """
    Tracks external API endpoint availability and failures.
    open: true (disabled/failing), false (active/healthy)
    """

    _providers: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _get_provider_state(cls, host: str) -> Dict[str, Any]:
        if host not in cls._providers:
            cls._providers[host] = {
                "consecutive_fails": 0,
                "disabled_until": 0,
                "open": False,
            }
        return cls._providers[host]

    @classmethod
    def is_available(cls, url_or_host: str) -> bool:
        if not url_or_host:
            return False
        host = urllib.parse.urlparse(url_or_host).netloc or url_or_host
        state = cls._get_provider_state(host)
        now = time.time()
        if state["disabled_until"] > now:
            return False
        if state["disabled_until"] != 0 and state["disabled_until"] <= now:
            # Half-open test transition
            state["disabled_until"] = 0
            state["open"] = False
        return not state["open"]

    @classmethod
    def record_failure(cls, url_or_host: str, error_type: str = "general", status_code: Optional[int] = None, retry_after: Optional[int] = None):
        if not url_or_host:
            return
        host = urllib.parse.urlparse(url_or_host).netloc or url_or_host
        state = cls._get_provider_state(host)
        now = time.time()
        state["consecutive_fails"] += 1

        disable_duration = 300  # Default 5 minutes for general 5xx / failures

        if error_type == "dns" or "name or service not known" in str(error_type).lower():
            disable_duration = 1800  # 30 minutes for DNS failure
        elif status_code == 429 or error_type == "rate_limit":
            disable_duration = retry_after if retry_after and retry_after > 0 else 600
        elif status_code and 500 <= status_code < 600:
            disable_duration = 300

        if state["consecutive_fails"] >= 3 or error_type == "dns":
            state["open"] = True
            state["disabled_until"] = now + disable_duration
            LOGGER(__name__).warning(f"[CIRCUIT-BREAKER] Circuit opened for host '{host}' (disabled for {disable_duration}s). Failure: {error_type}")

    @classmethod
    def record_success(cls, url_or_host: str):
        if not url_or_host:
            return
        host = urllib.parse.urlparse(url_or_host).netloc or url_or_host
        state = cls._get_provider_state(host)
        state["consecutive_fails"] = 0
        state["disabled_until"] = 0
        state["open"] = False


class AudioCache:
    """
    JSON file cache storing YouTube track download records:
    key = youtube video_id
    value = {source, video_id, title, duration, telegram_file_id, local_path}
    """

    _cache: Dict[str, Dict[str, Any]] = {}
    _loaded: bool = False

    @classmethod
    def _load(cls):
        if cls._loaded:
            return
        os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
        if os.path.exists(CACHE_FILE_PATH):
            try:
                with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                    cls._cache = json.load(f)
            except Exception as e:
                LOGGER(__name__).error(f"[AUDIO-CACHE] Error loading audio cache: {e}")
                cls._cache = {}
        cls._loaded = True

    @classmethod
    def _save(cls):
        os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
        try:
            with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(cls._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            LOGGER(__name__).error(f"[AUDIO-CACHE] Error saving audio cache: {e}")

    @classmethod
    def get(cls, video_id: str) -> Optional[Dict[str, Any]]:
        cls._load()
        if not video_id:
            return None
        item = cls._cache.get(video_id)
        if not item:
            return None

        local_path = item.get("local_path")
        if local_path and os.path.exists(local_path) and os.path.getsize(local_path) > 1024:
            return item
        elif item.get("telegram_file_id"):
            return item

        # Invalidate missing file entry
        cls._cache.pop(video_id, None)
        cls._save()
        return None

    @classmethod
    def set(
        cls,
        video_id: str,
        local_path: Optional[str] = None,
        title: str = "",
        duration: Union[int, str] = 0,
        source: str = "youtube",
        telegram_file_id: Optional[str] = None,
    ):
        cls._load()
        if not video_id:
            return
        cls._cache[video_id] = {
            "source": source,
            "video_id": video_id,
            "title": title,
            "duration": duration,
            "telegram_file_id": telegram_file_id,
            "local_path": local_path,
            "cached_at": time.time(),
        }
        cls._save()
        LOGGER(__name__).info(f"[AUDIO-CACHE] Cached track record for video_id: {video_id}")

# In-memory session cache for cookie usability testing
_UNUSABLE_COOKIES: Set[str] = set()
_TESTED_COOKIES: Dict[str, bool] = {}


def is_bgutil_server_running() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", 4416)) == 0:
                return True
    except Exception:
        pass

    try:
        res = subprocess.run(["pgrep", "-f", "bgutil.*server|bgutil-ytdlp"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            pids = res.stdout.strip().split()
            current_pid = str(os.getpid())
            if any(pid != current_pid for pid in pids):
                return True
    except Exception:
        pass
    return False


def get_ffmpeg_path() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path
    candidates = [
        "/home/jules/.local/share/ffmpeg_bin/ffmpeg",
        os.path.expanduser("~/.local/share/ffmpeg_bin/ffmpeg"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for c in candidates:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


def get_ffmpeg_version() -> str:
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        return "NOT INSTALLED"
    try:
        res = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            first_line = res.stdout.splitlines()[0]
            return first_line.split("version")[1].strip().split()[0] if "version" in first_line else first_line[:30]
    except Exception:
        pass
    return "INSTALLED (Version Unknown)"


def get_yt_dlp_version() -> str:
    try:
        import yt_dlp.version
        return getattr(yt_dlp.version, "__version__", "Unknown")
    except Exception:
        try:
            return getattr(yt_dlp, "__version__", "Unknown")
        except Exception:
            return "Unknown"


def get_ytdl_base_opts(
    cookie_file: Optional[str] = None,
    is_video: bool = False,
    use_oauth2: bool = False,
    player_clients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Centralized yt-dlp configuration generator.
    Uses dynamic audio format selector 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best' with format_sort.
    Configures client spoofing and optional FFmpeg post-processing.
    """
    format_selector = (
        "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        if is_video
        else "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
    )

    if not player_clients:
        player_clients = ["ios", "mweb", "android", "tv"] if not cookie_file else ["ios", "android", "mweb"]

    yt_extractor_args: Dict[str, Any] = {
        "player_client": player_clients,
        "player_skip": ["webpage", "configs"],
    }

    pot_url = getattr(config, "POT_PROVIDER_URL", "http://127.0.0.1:4416")
    if is_bgutil_server_running() and pot_url:
        yt_extractor_args["po_token"] = [f"web+{pot_url}"]

    opts = {
        "format": format_selector,
        "format_sort": ["res", "ext:m4a:m4a", "acodec"],
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
        "extractor_args": {"youtube": yt_extractor_args},
    }

    if use_oauth2:
        opts["username"] = "oauth2"

    if not is_bgutil_server_running():
        opts["no_plugins"] = True

    ff_path = get_ffmpeg_path()
    if ff_path:
        opts["ffmpeg_location"] = ff_path
        if not is_video:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]

    if cookie_file:
        abs_cookie = os.path.abspath(cookie_file)
        if os.path.exists(abs_cookie) and os.path.getsize(abs_cookie) > 0:
            opts["cookiefile"] = abs_cookie

    return opts


def classify_ytdl_error(error_msg_or_exc: Union[str, Exception]) -> Tuple[str, str]:
    msg = str(error_msg_or_exc)
    msg_lower = msg.lower()

    if "name or service not known" in msg_lower or "gaierror" in msg_lower or "nodename nor servname provided" in msg_lower:
        return "DNS_ERROR", "DNS resolution failed for host."

    if "requested format is not available" in msg_lower or "no formats found" in msg_lower or ("format" in msg_lower and "not available" in msg_lower):
        return "FORMAT_ERROR", "Requested audio/video format is not available for this track."

    if "sign in to confirm you're not a bot" in msg_lower or "botguard" in msg_lower or "po_token" in msg_lower or "confirm you're not a bot" in msg_lower:
        return "BOT_CHECK", "YouTube bot detection triggered requiring verification."

    if "login_required" in msg_lower or "use --cookies" in msg_lower or "player response login_required" in msg_lower or "private video" in msg_lower:
        return "AUTH_REQUIRED", "YouTube authentication required or missing/expired cookies."

    if "video unavailable" in msg_lower or "copyright" in msg_lower or "removed" in msg_lower or "this video is unavailable" in msg_lower:
        return "VIDEO_UNAVAILABLE", "Video is unavailable or restricted."

    if "429" in msg_lower or "too many requests" in msg_lower or "rate limit" in msg_lower:
        return "RATE_LIMIT", "YouTube rate limit encountered."

    if "403" in msg_lower or "forbidden" in msg_lower or "http error 403" in msg_lower:
        return "HTTP_403", "HTTP 403 Forbidden received from endpoint."

    if "expired" in msg_lower:
        return "EXPIRED_STREAM", "Stream URL or request expired."

    if "socket" in msg_lower or "timeout" in msg_lower or "connection" in msg_lower or "http error" in msg_lower:
        return "NETWORK_ERROR", "Network failure or timeout during extraction."

    return "UNKNOWN_ERROR", msg


def mark_cookie_unusable(cookie_path: str):
    abs_p = os.path.abspath(cookie_path)
    _UNUSABLE_COOKIES.add(abs_p)
    _TESTED_COOKIES[abs_p] = False


def mark_cookie_usable(cookie_path: str):
    abs_p = os.path.abspath(cookie_path)
    if abs_p in _UNUSABLE_COOKIES:
        _UNUSABLE_COOKIES.remove(abs_p)
    _TESTED_COOKIES[abs_p] = True


def is_cookie_usable(cookie_path: str) -> bool:
    abs_p = os.path.abspath(cookie_path)
    return abs_p not in _UNUSABLE_COOKIES


def test_cookie_file(cookie_path: str, force_test: bool = False) -> bool:
    """Lightweight extraction test to verify if yt-dlp cookie authentication actually works."""
    abs_p = os.path.abspath(cookie_path)
    if not force_test and abs_p in _TESTED_COOKIES:
        return _TESTED_COOKIES[abs_p]

    if not os.path.exists(abs_p) or os.path.getsize(abs_p) == 0:
        mark_cookie_unusable(abs_p)
        return False

    opts = get_ytdl_base_opts(abs_p)
    test_url = "https://www.youtube.com/watch?v=hHuG7FIKgtc"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(test_url, download=False)
        mark_cookie_usable(abs_p)
        return True
    except Exception as e:
        err_cat, _ = classify_ytdl_error(e)
        if err_cat in ("BOT_CHECK", "AUTH_REQUIRED"):
            mark_cookie_unusable(abs_p)
            return False
        # If it's a network glitch or non-auth issue, keep it tentatively allowed
        _TESTED_COOKIES[abs_p] = True
        return True


def get_cookie_files() -> List[str]:
    """Returns all available and non-empty cookie file paths in order of preference."""
    candidates = []

    env_cookie = os.environ.get("YOUTUBE_COOKIES")
    if env_cookie:
        candidates.append(env_cookie)

    project_paths = [
        "cookies/cookies.txt",
        "SONALI_MUSIC/assets/cookies.txt",
        "assets/cookies.txt",
    ]
    candidates.extend(project_paths)

    existing_files = []
    seen = set()
    for path in candidates:
        abs_p = os.path.abspath(path)
        if abs_p not in seen and os.path.exists(abs_p) and os.path.getsize(abs_p) > 0:
            existing_files.append(abs_p)
            seen.add(abs_p)

    return existing_files


def get_cookie_file() -> Optional[str]:
    valid_files = get_valid_cookie_files()
    if valid_files:
        return valid_files[0]
    all_files = get_cookie_files()
    return all_files[0] if all_files else None


def analyze_cookies(cookie_path: Optional[str] = None, run_extraction_test: bool = False) -> Dict[str, Any]:
    if not cookie_path:
        cookie_path = get_cookie_file()

    result = {
        "exists": False,
        "valid_format": False,
        "youtube_count": 0,
        "auth_count": 0,
        "missing_auth_cookies": sorted(list(REQUIRED_AUTH_COOKIES)),
        "found_auth_cookie_names": [],
        "found_visitor_cookie_names": [],
        "status": "MISSING",
        "extraction_test": "SKIPPED",
        "cookie_path": cookie_path,
        "file_size": 0,
    }

    if not cookie_path or not os.path.exists(cookie_path):
        return result

    file_size = os.path.getsize(cookie_path)
    result["exists"] = True
    result["file_size"] = file_size

    if file_size == 0:
        return result

    now = time.time()
    yt_cookie_names = set()
    found_auth_cookies = set()
    found_visitor_cookies = set()
    has_netscape_header = False
    valid_lines = 0

    try:
        with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                if "# Netscape HTTP Cookie File" in line or "# HTTP Cookie File" in line:
                    has_netscape_header = True
                    continue
                if line_str.startswith("#HttpOnly_"):
                    line_str = line_str[len("#HttpOnly_"):]
                elif line_str.startswith("#"):
                    continue

                parts = line_str.split("\t")
                if len(parts) >= 7:
                    valid_lines += 1
                    domain = parts[0].strip()
                    expiry_str = parts[4].strip()
                    cookie_name = parts[5].strip()

                    if "youtube.com" in domain or "google.com" in domain:
                        try:
                            expiry = int(expiry_str)
                            if expiry > 0 and expiry < now:
                                continue
                        except ValueError:
                            pass

                        yt_cookie_names.add(cookie_name)
                        if cookie_name in REQUIRED_AUTH_COOKIES:
                            found_auth_cookies.add(cookie_name)
                        if cookie_name in VISITOR_COOKIE_NAMES:
                            found_visitor_cookies.add(cookie_name)

        result["valid_format"] = has_netscape_header or (valid_lines > 0)
        result["youtube_count"] = len(yt_cookie_names)
        result["auth_count"] = len(found_auth_cookies)
        result["missing_auth_cookies"] = sorted(list(REQUIRED_AUTH_COOKIES - found_auth_cookies))
        result["found_auth_cookie_names"] = sorted(list(found_auth_cookies))
        result["found_visitor_cookie_names"] = sorted(list(found_visitor_cookies))

        if result["auth_count"] == len(REQUIRED_AUTH_COOKIES) and result["youtube_count"] > 0:
            result["status"] = "VALID"
        elif result["youtube_count"] > 0:
            result["status"] = "INCOMPLETE"
        else:
            result["status"] = "INVALID"

        if run_extraction_test:
            test_pass = test_cookie_file(cookie_path)
            result["extraction_test"] = "PASS" if test_pass else "FAIL"

    except Exception as e:
        LOGGER(__name__).error(f"Error analyzing cookie file {cookie_path}: {e}")
        result["status"] = "INVALID"

    return result


def get_valid_cookie_files(filter_unusable: bool = True) -> List[str]:
    valid_files = []
    incomplete_files = []

    for c_path in get_cookie_files():
        if filter_unusable and not is_cookie_usable(c_path):
            continue
        analysis = analyze_cookies(c_path)
        if analysis["status"] == "VALID":
            valid_files.append(c_path)
        elif analysis["status"] == "INCOMPLETE":
            incomplete_files.append(c_path)

    return valid_files if valid_files else incomplete_files


def check_bgutil_and_potoken() -> Dict[str, Any]:
    bgutil_paths = [
        "/root/bgutil-ytdlp-pot-provider",
        "./bgutil-ytdlp-pot-provider",
        os.path.expanduser("~/bgutil-ytdlp-pot-provider"),
    ]
    bgutil_dir_exists = any(os.path.exists(p) for p in bgutil_paths)

    node_path = shutil.which("node")
    node_available = node_path is not None

    deno_path = shutil.which("deno")
    deno_available = deno_path is not None

    bgutil_server_running = is_bgutil_server_running()

    if bgutil_server_running:
        potoken_status = "OK (Server Running)"
    elif bgutil_dir_exists:
        potoken_status = "DISABLED (Server Not Running)"
    else:
        potoken_status = "NOT_INSTALLED"

    return {
        "bgutil_dir_exists": bgutil_dir_exists,
        "node_available": node_available,
        "deno_available": deno_available,
        "bgutil_server_running": bgutil_server_running,
        "potoken_provider_status": potoken_status,
    }


def log_startup_diagnostics() -> Dict[str, Any]:
    yt_ver = get_yt_dlp_version()
    ff_ver = get_ffmpeg_version()
    cookie_files = get_cookie_files()
    valid_cookies = get_valid_cookie_files()
    pot_info = check_bgutil_and_potoken()

    LOGGER(__name__).info("======== YouTube Extraction System Diagnostics ========")
    LOGGER(__name__).info(f"[YT-DIAG] yt-dlp Version          : {yt_ver}")
    LOGGER(__name__).info(f"[YT-DIAG] FFmpeg Status           : {ff_ver}")
    LOGGER(__name__).info(f"[YT-AUTH] Found Cookie Files      : {len(cookie_files)}")
    LOGGER(__name__).info(f"[YT-AUTH] Usable Cookie Files     : {len(valid_cookies)}")

    for idx, c_path in enumerate(cookie_files, 1):
        c_info = analyze_cookies(c_path, run_extraction_test=False)
        usable_str = "USABLE" if is_cookie_usable(c_path) else "UNUSABLE"
        LOGGER(__name__).info(f"[YT-AUTH] Cookie #{idx} ({os.path.basename(c_path)}) : {c_info['status']} ({c_info['auth_count']}/{len(REQUIRED_AUTH_COOKIES)} auth cookies) [{usable_str}]")

    LOGGER(__name__).info(f"[YT-PO] PO Token Provider Status : {pot_info['potoken_provider_status']}")
    LOGGER(__name__).info("=======================================================")

    return {
        "yt_version": yt_ver,
        "ffmpeg_version": ff_ver,
        "cookie_files": cookie_files,
        "valid_cookies": valid_cookies,
        "pot_info": pot_info,
    }


def get_health_status() -> str:
    yt_ver = get_yt_dlp_version()
    ff_ver = get_ffmpeg_version()
    cookie_files = get_cookie_files()
    valid_cookies = get_valid_cookie_files()
    pot_info = check_bgutil_and_potoken()

    yt_status = "OK" if yt_ver != "Unknown" else "ERROR"
    ff_status = "OK" if "NOT INSTALLED" not in ff_ver else "MISSING"
    cookie_status = "VALID" if len(valid_cookies) > 0 else ("INCOMPLETE" if len(cookie_files) > 0 else "MISSING")
    pot_status = "OK" if "OK" in pot_info["potoken_provider_status"] else "WARNING"
    bgutil_status = "OK" if pot_info["bgutil_dir_exists"] or pot_info["bgutil_server_running"] else "NOT INSTALLED"

    msg = (
        "<b>📊 YouTube System Health Check</b>\n\n"
        f"<b>YT-DLP:</b> {yt_status} ({yt_ver})\n"
        f"<b>FFMPEG:</b> {ff_status}\n"
        f"<b>Cookie Files:</b> {len(cookie_files)} total ({len(valid_cookies)} usable)\n"
        f"<b>Cookies Status:</b> {cookie_status}\n"
        f"<b>PO Token:</b> {pot_status}\n"
        f"<b>BGUTIL:</b> {bgutil_status}\n"
    )
    return msg


def get_cookiecheck_status() -> str:
    cookie_files = get_cookie_files()
    if not cookie_files:
        return "<b>🍪 Cookie Validation Status</b>\n\n⚠️ No cookie files found in repository."

    msg = "<b>🍪 Cookie Validation Status</b>\n\n"
    for idx, c_path in enumerate(cookie_files, 1):
        c_info = analyze_cookies(c_path, run_extraction_test=False)
        file_ok = "FOUND" if c_info["exists"] else "MISSING"
        format_ok = "PARSEABLE" if c_info["valid_format"] else "INVALID_FORMAT"
        contains_yt = "CONTAINS_YOUTUBE_COOKIES" if c_info["youtube_count"] > 0 else "NO_YOUTUBE_COOKIES"
        test_status = "PASS" if is_cookie_usable(c_path) else "FAIL"

        msg += (
            f"<b>Cookie #{idx}:</b> <code>{os.path.basename(c_path)}</code>\n"
            f"<b>File:</b> {file_ok} | <b>Format:</b> {format_ok}\n"
            f"<b>YouTube Cookies:</b> {contains_yt}\n"
            f"<b>Auth Cookies:</b> {c_info['auth_count']} / {len(REQUIRED_AUTH_COOKIES)}\n"
            f"<b>EXTRACTION_TEST:</b> {test_status}\n\n"
        )

    valid_count = len(get_valid_cookie_files())
    msg += f"<b>Multi-Cookie Backup Mode:</b> {'Active (' + str(valid_count) + ' ready)' if valid_count > 0 else 'Disabled'}\n"
    return msg
