import os
import shutil
import time
import subprocess
from typing import Dict, Any, Optional, Tuple, List, Union
import yt_dlp
from SONALI_MUSIC import LOGGER

REQUIRED_AUTH_COOKIES = {"SID", "SSID", "SAPISID", "__Secure-1PSID", "__Secure-3PSID"}


def get_cookie_file() -> Optional[str]:
    for path in ["cookies/cookies.txt", "SONALI_MUSIC/assets/cookies.txt", "assets/cookies.txt"]:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path) and os.path.getsize(abs_path) > 0:
            return abs_path
    return None


def analyze_cookies(cookie_path: Optional[str] = None) -> Dict[str, Any]:
    if not cookie_path:
        cookie_path = get_cookie_file()

    result = {
        "exists": False,
        "valid_format": False,
        "youtube_count": 0,
        "auth_count": 0,
        "missing_auth_cookies": list(REQUIRED_AUTH_COOKIES),
        "status": "MISSING",
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
                if line_str.startswith("#"):
                    continue

                parts = line_str.split("\t")
                if len(parts) >= 7:
                    valid_lines += 1
                    domain = parts[0].strip()
                    expiry_str = parts[4].strip()
                    cookie_name = parts[5].strip()

                    # Check domain
                    if "youtube.com" in domain or "google.com" in domain:
                        # Check expiry
                        try:
                            expiry = int(expiry_str)
                            if expiry > 0 and expiry < now:
                                continue  # Expired
                        except ValueError:
                            pass

                        yt_cookie_names.add(cookie_name)
                        if cookie_name in REQUIRED_AUTH_COOKIES:
                            found_auth_cookies.add(cookie_name)

        result["valid_format"] = has_netscape_header or (valid_lines > 0)
        result["youtube_count"] = len(yt_cookie_names)
        result["auth_count"] = len(found_auth_cookies)
        result["missing_auth_cookies"] = sorted(list(REQUIRED_AUTH_COOKIES - found_auth_cookies))

        if result["auth_count"] == len(REQUIRED_AUTH_COOKIES) and result["youtube_count"] > 0:
            result["status"] = "VALID"
        else:
            result["status"] = "INVALID"

    except Exception as e:
        LOGGER(__name__).error(f"Error analyzing cookie file: {e}")
        result["status"] = "INVALID"

    return result


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

    bgutil_server_running = False
    try:
        # Check if local bgutil server or provider process is running
        res = subprocess.run(["pgrep", "-f", "bgutil"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            bgutil_server_running = True
    except Exception:
        pass

    if bgutil_server_running:
        potoken_status = "OK"
    elif bgutil_dir_exists and (node_available or deno_available):
        potoken_status = "OK (Provider Ready)"
    elif bgutil_dir_exists:
        potoken_status = "MISSING_RUNTIME (Node/Deno required)"
    else:
        potoken_status = "NOT_INSTALLED"

    return {
        "bgutil_dir_exists": bgutil_dir_exists,
        "node_available": node_available,
        "deno_available": deno_available,
        "bgutil_server_running": bgutil_server_running,
        "potoken_provider_status": potoken_status,
    }


def get_yt_dlp_version() -> str:
    try:
        return yt_dlp.__version__
    except Exception:
        return "Unknown"


def get_ffmpeg_version() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return "NOT INSTALLED"
    try:
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            first_line = res.stdout.splitlines()[0]
            return first_line.split("version")[1].strip().split()[0] if "version" in first_line else first_line[:30]
    except Exception:
        pass
    return "INSTALLED (Version Unknown)"


def classify_ytdl_error(error_msg_or_exc: Union[str, Exception]) -> Tuple[str, str]:
    msg = str(error_msg_or_exc)
    msg_lower = msg.lower()

    if "login_required" in msg_lower or "sign in to confirm you're not a bot" in msg_lower or "use --cookies" in msg_lower:
        return "AUTH_REQUIRED", "Missing/expired authentication cookies."
    if "po_token" in msg_lower or "pot" in msg_lower or "botguard" in msg_lower:
        return "POTOKEN_REQUIRED", "PO Token provider failure or token missing."

    return "EXTRACTION_FAILED", msg


def log_startup_diagnostics() -> Dict[str, Any]:
    yt_ver = get_yt_dlp_version()
    ff_ver = get_ffmpeg_version()
    cookie_info = analyze_cookies()
    pot_info = check_bgutil_and_potoken()

    LOGGER(__name__).info("======== YouTube Extraction System Diagnostics ========")
    LOGGER(__name__).info(f"yt-dlp Version          : {yt_ver}")
    LOGGER(__name__).info(f"FFmpeg Status           : {ff_ver}")
    LOGGER(__name__).info(f"Cookie Path             : {cookie_info['cookie_path'] or 'None'}")
    LOGGER(__name__).info(f"Cookie File Exists      : {cookie_info['exists']}")
    LOGGER(__name__).info(f"Cookie File Size        : {cookie_info['file_size']} bytes")
    LOGGER(__name__).info(f"YouTube Cookies Count   : {cookie_info['youtube_count']}")
    LOGGER(__name__).info(f"Auth Cookies Count      : {cookie_info['auth_count']} / {len(REQUIRED_AUTH_COOKIES)}")
    LOGGER(__name__).info(f"Missing Auth Cookies    : {', '.join(cookie_info['missing_auth_cookies']) if cookie_info['missing_auth_cookies'] else 'None'}")
    LOGGER(__name__).info(f"Cookie Overall Status   : {cookie_info['status']}")
    LOGGER(__name__).info(f"PO Token Provider Status: {pot_info['potoken_provider_status']}")
    LOGGER(__name__).info("=======================================================")

    if cookie_info["status"] != "VALID":
        LOGGER(__name__).warning("⚠️ YouTube authentication cookies are missing or invalid in cookies.txt!")
        LOGGER(__name__).warning("⚠️ Authentication cookies required: " + ", ".join(REQUIRED_AUTH_COOKIES))

    return {
        "yt_version": yt_ver,
        "ffmpeg_version": ff_ver,
        "cookie_info": cookie_info,
        "pot_info": pot_info,
    }


def get_health_status() -> str:
    yt_ver = get_yt_dlp_version()
    ff_ver = get_ffmpeg_version()
    cookie_info = analyze_cookies()
    pot_info = check_bgutil_and_potoken()

    yt_status = "OK" if yt_ver != "Unknown" else "ERROR"
    ff_status = "OK" if "NOT INSTALLED" not in ff_ver else "MISSING"
    cookie_status = cookie_info["status"]
    auth_status = "OK" if cookie_info["auth_count"] == len(REQUIRED_AUTH_COOKIES) else "Missing"
    pot_status = "OK" if "OK" in pot_info["potoken_provider_status"] else "WARNING"
    bgutil_status = "OK" if pot_info["bgutil_dir_exists"] or pot_info["bgutil_server_running"] else "NOT INSTALLED"

    msg = (
        "<b>📊 YouTube System Health Check</b>\n\n"
        f"<b>YT-DLP:</b> {yt_status} ({yt_ver})\n"
        f"<b>FFMPEG:</b> {ff_status}\n"
        f"<b>Cookies:</b> {cookie_status}\n"
        f"<b>Auth Cookies:</b> {auth_status}\n"
        f"<b>PO Token:</b> {pot_status}\n"
        f"<b>BGUTIL:</b> {bgutil_status}\n"
    )
    return msg


def get_cookiecheck_status() -> str:
    cookie_info = analyze_cookies()

    file_ok = "OK" if cookie_info["exists"] else "MISSING"
    format_ok = "OK" if cookie_info["valid_format"] else "INVALID"

    msg = (
        "<b>🍪 Cookie Validation Status</b>\n\n"
        f"<b>Cookie File:</b> {file_ok}\n"
        f"<b>Format:</b> {format_ok}\n"
        f"<b>YouTube Cookies:</b> {cookie_info['youtube_count']}\n"
        f"<b>Auth Cookies:</b> {cookie_info['auth_count']} / {len(REQUIRED_AUTH_COOKIES)}\n"
        f"<b>Status:</b> {cookie_info['status']}\n"
    )

    if cookie_info["status"] != "VALID":
        msg += f"\n<b>Missing Auth Cookies:</b> <code>{', '.join(cookie_info['missing_auth_cookies'])}</code>\n"
        msg += "\n⚠️ <b>Notice:</b> YouTube authentication cookies missing or invalid. Please update <code>cookies.txt</code> with full account session cookies."

    return msg
