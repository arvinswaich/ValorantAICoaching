import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


APP_VERSION = "1.0.1"
REPOSITORY = "arvinswaich/ValorantAICoaching"
RELEASE_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
EXPECTED_ASSET_NAME = "ValorantVODCoach.exe"
CHECK_INTERVAL_SECONDS = 6 * 60 * 60
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024


def is_packaged_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def parse_version(value: str) -> tuple:
    cleaned = (value or "").strip().lower().lstrip("v")
    core = cleaned.split("-", 1)[0]
    parts = []
    for item in core.split("."):
        digits = "".join(character for character in item if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple((parts + [0, 0, 0])[:3])


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    return parse_version(candidate) > parse_version(current)


def find_windows_asset(release: dict) -> dict | None:
    for asset in release.get("assets", []):
        if asset.get("name", "").lower() == EXPECTED_ASSET_NAME.lower():
            return asset
    return None


def fetch_update_info(timeout_seconds: int = 8) -> dict:
    request = urllib.request.Request(
        RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ValorantVODCoach/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        release = json.loads(response.read().decode("utf-8"))

    tag_name = release.get("tag_name", "")
    asset = find_windows_asset(release)
    return {
        "available": bool(asset and is_newer_version(tag_name)),
        "current_version": APP_VERSION,
        "latest_version": tag_name.lstrip("v") or "unknown",
        "release_name": release.get("name") or tag_name,
        "release_url": release.get("html_url"),
        "release_notes": release.get("body") or "",
        "asset": asset,
    }


def download_update(update_info: dict) -> Path:
    asset = update_info.get("asset") or {}
    download_url = asset.get("browser_download_url")
    if not download_url:
        raise RuntimeError("The release does not contain a Windows executable.")

    expected_size = int(asset.get("size") or 0)
    if expected_size > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("The update file is unexpectedly large.")

    update_directory = _update_directory()
    update_directory.mkdir(parents=True, exist_ok=True)
    destination = update_directory / f"ValorantVODCoach-{update_info['latest_version']}-update.exe"
    temporary_destination = destination.with_suffix(".download")

    request = urllib.request.Request(
        download_url,
        headers={"User-Agent": f"ValorantVODCoach/{APP_VERSION}"},
    )
    digest = hashlib.sha256()
    bytes_written = 0
    try:
        with urllib.request.urlopen(request, timeout=30) as response, temporary_destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError("The update download exceeded the allowed size.")
                digest.update(chunk)
                output.write(chunk)

        if expected_size and bytes_written != expected_size:
            raise RuntimeError("The downloaded update size does not match the GitHub release.")
        verify_digest(digest.hexdigest(), asset.get("digest"))
        temporary_destination.replace(destination)
        return destination
    except Exception:
        temporary_destination.unlink(missing_ok=True)
        raise


def verify_digest(actual_sha256: str, expected_digest: str | None) -> None:
    if not expected_digest:
        return
    algorithm, separator, expected_value = expected_digest.partition(":")
    if separator and algorithm.lower() == "sha256":
        if actual_sha256.lower() != expected_value.lower():
            raise RuntimeError("The downloaded update failed its SHA-256 integrity check.")


def launch_update_installer(update_path: Path) -> None:
    if not is_packaged_app():
        raise RuntimeError("Automatic installation is only available in the packaged Windows app.")
    target_path = Path(sys.executable).resolve()
    subprocess.Popen(
        [
            str(update_path),
            "--apply-update",
            str(os.getpid()),
            str(target_path),
        ],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def apply_update(parent_pid: int, target_path: str) -> int:
    source_path = Path(sys.executable).resolve()
    destination = Path(target_path).resolve()
    if destination.name.lower() != EXPECTED_ASSET_NAME.lower():
        return 2

    _wait_for_process(parent_pid, timeout_milliseconds=60_000)
    destination.parent.mkdir(parents=True, exist_ok=True)

    last_error = None
    for _attempt in range(40):
        try:
            shutil.copy2(source_path, destination)
            last_error = None
            break
        except OSError as error:
            last_error = error
            time.sleep(0.25)
    if last_error is not None:
        return 3

    subprocess.Popen([str(destination)], close_fds=True)
    return 0


def handle_update_arguments(arguments: list[str] | None = None) -> bool:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if len(arguments) == 3 and arguments[0] == "--apply-update":
        exit_code = apply_update(int(arguments[1]), arguments[2])
        raise SystemExit(exit_code)
    return False


def should_check_automatically() -> bool:
    if not is_packaged_app():
        return False
    state_path = _state_path()
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        last_check = float(state.get("last_check", 0))
    except (OSError, ValueError, TypeError):
        return True
    return time.time() - last_check >= CHECK_INTERVAL_SECONDS


def mark_update_check_complete() -> None:
    state_path = _state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"last_check": time.time()}), encoding="utf-8")


def cleanup_stale_updates(max_age_seconds: int = 7 * 24 * 60 * 60) -> None:
    update_directory = _update_directory()
    if not update_directory.exists():
        return
    cutoff = time.time() - max_age_seconds
    for path in update_directory.glob("ValorantVODCoach-*-update.exe"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def _app_data_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ValorantVODCoach"
    return Path(tempfile.gettempdir()) / "ValorantVODCoach"


def _update_directory() -> Path:
    return _app_data_directory() / "updates"


def _state_path() -> Path:
    return _app_data_directory() / "update-state.json"


def _wait_for_process(process_id: int, timeout_milliseconds: int) -> None:
    if os.name != "nt":
        time.sleep(1)
        return
    synchronize = 0x00100000
    process_handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, process_id)
    if not process_handle:
        return
    try:
        ctypes.windll.kernel32.WaitForSingleObject(process_handle, timeout_milliseconds)
    finally:
        ctypes.windll.kernel32.CloseHandle(process_handle)
