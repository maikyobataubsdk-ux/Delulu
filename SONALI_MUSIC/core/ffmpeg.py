import os
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile


def ensure_ffmpeg():
    # 1. Check if ffmpeg and ffprobe are already in system PATH
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return

    # 2. Check if we already have them in a local bin or a fallback folder
    home = os.path.expanduser("~")
    possible_dirs = [
        os.path.join(home, ".local", "bin"),
        os.path.join(home, "bin"),
        os.path.join(os.getcwd(), "bin"),
        os.path.join(home, ".local", "share", "ffmpeg_bin"),
    ]

    for d in possible_dirs:
        if d not in os.environ["PATH"]:
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
        if shutil.which("ffmpeg") and shutil.which("ffprobe"):
            return

    # 3. If still not found, download the static binaries automatically
    target_dir = os.path.join(home, ".local", "share", "ffmpeg_bin")
    os.makedirs(target_dir, exist_ok=True)

    system = platform.system().lower()
    arch = platform.machine().lower()

    ffmpeg_name = "ffmpeg.exe" if "windows" in system else "ffmpeg"
    ffprobe_name = "ffprobe.exe" if "windows" in system else "ffprobe"

    ffmpeg_path = os.path.join(target_dir, ffmpeg_name)
    ffprobe_path = os.path.join(target_dir, ffprobe_name)

    # Double check if binaries are already present in target_dir but target_dir wasn't in PATH
    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        if target_dir not in os.environ["PATH"]:
            os.environ["PATH"] = target_dir + os.pathsep + os.environ["PATH"]
        return

    print("==========================================================")
    print("FFmpeg and/or FFprobe not found on your system!")
    print("Automatically downloading static builds to resolve this...")
    print("==========================================================")

    try:
        if "linux" in system:
            if "arm" in arch or "aarch64" in arch:
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
            else:
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

            archive_path = os.path.join(target_dir, "ffmpeg.tar.xz")
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response, open(
                archive_path, "wb"
            ) as out_file:
                out_file.write(response.read())

            with tarfile.open(archive_path, "r:xz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("/ffmpeg") or member.name.endswith(
                        "/ffprobe"
                    ):
                        member.name = os.path.basename(member.name)
                        tar.extract(member, path=target_dir)

            os.chmod(ffmpeg_path, 0o755)
            os.chmod(ffprobe_path, 0o755)
            os.remove(archive_path)

        elif "windows" in system:
            url = "https://github.com/GyanD/codexffmpeg/releases/download/6.0/ffmpeg-6.0-full_build.zip"
            archive_path = os.path.join(target_dir, "ffmpeg.zip")
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response, open(
                archive_path, "wb"
            ) as out_file:
                out_file.write(response.read())

            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    if member.endswith("ffmpeg.exe") or member.endswith(
                        "ffprobe.exe"
                    ):
                        filename = os.path.basename(member)
                        source = zip_ref.open(member)
                        target = open(os.path.join(target_dir, filename), "wb")
                        with source, target:
                            shutil.copyfileobj(source, target)

            os.remove(archive_path)

        elif "darwin" in system:  # macOS
            # Evermeet has static builds for macOS
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            archive_path = os.path.join(target_dir, "ffmpeg.zip")
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response, open(
                archive_path, "wb"
            ) as out_file:
                out_file.write(response.read())

            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)

            os.remove(archive_path)

            # ffprobe for macOS
            url_probe = "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
            probe_archive_path = os.path.join(target_dir, "ffprobe.zip")
            req_probe = urllib.request.Request(
                url_probe, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req_probe) as response, open(
                probe_archive_path, "wb"
            ) as out_file:
                out_file.write(response.read())

            with zipfile.ZipFile(probe_archive_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)

            os.remove(probe_archive_path)

            os.chmod(ffmpeg_path, 0o755)
            os.chmod(ffprobe_path, 0o755)

        else:
            print("Unsupported platform. Please install ffmpeg and ffprobe manually.")
            return

        if target_dir not in os.environ["PATH"]:
            os.environ["PATH"] = target_dir + os.pathsep + os.environ["PATH"]

        print("==========================================================")
        print("FFmpeg and FFprobe successfully downloaded and configured!")
        print("==========================================================")

    except Exception as e:
        print(f"Error downloading/extracting ffmpeg/ffprobe: {e}")
