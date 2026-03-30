import json
import os
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

APP_ROOT = Path(__file__).resolve().parent
SELENIUM_CACHE = APP_ROOT / ".selenium"
LATEST_META_URL = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"


@contextmanager
def file_lock(lock_path: Path):
    """
    Simple inter-process lock for multi-worker Flask/Gunicorn.
    Linux-only, good for RHEL.
    """
    import fcntl

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def _extract_zip(zip_path: Path, extract_to: Path) -> None:
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)


def _find_file(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not find {name} under {root}")
    return matches[0]


def ensure_latest_chrome_runtime() -> tuple[str, str]:
    """
    Returns:
        (chrome_binary_path, chromedriver_path)
    """
    SELENIUM_CACHE.mkdir(parents=True, exist_ok=True)

    lock_file = SELENIUM_CACHE / ".download.lock"
    with file_lock(lock_file):
        with urllib.request.urlopen(LATEST_META_URL, timeout=60) as resp:
            meta = json.load(resp)

        stable = meta["channels"]["Stable"]
        version = stable["version"]

        chrome_url = None
        driver_url = None

        for item in stable["downloads"]["chrome"]:
            if item["platform"] == "linux64":
                chrome_url = item["url"]
                break

        for item in stable["downloads"]["chromedriver"]:
            if item["platform"] == "linux64":
                driver_url = item["url"]
                break

        if not chrome_url or not driver_url:
            raise RuntimeError("Could not find linux64 Chrome/ChromeDriver download URLs")

        version_root = SELENIUM_CACHE / version
        browser_root = version_root / "chrome"
        driver_root = version_root / "driver"

        chrome_binary = browser_root / "chrome-linux64" / "chrome"
        chromedriver_binary = driver_root / "chromedriver-linux64" / "chromedriver"

        if chrome_binary.exists() and chromedriver_binary.exists():
            chromedriver_binary.chmod(chromedriver_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            chrome_binary.chmod(chrome_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return str(chrome_binary), str(chromedriver_binary)

        with tempfile.TemporaryDirectory(dir=SELENIUM_CACHE) as tmpdir:
            tmpdir = Path(tmpdir)

            chrome_zip = tmpdir / "chrome.zip"
            driver_zip = tmpdir / "chromedriver.zip"

            _download(chrome_url, chrome_zip)
            _download(driver_url, driver_zip)

            _extract_zip(chrome_zip, browser_root)
            _extract_zip(driver_zip, driver_root)

        chrome_binary = _find_file(browser_root, "chrome")
        chromedriver_binary = _find_file(driver_root, "chromedriver")

        chrome_binary.chmod(chrome_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        chromedriver_binary.chmod(chromedriver_binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Optional convenience symlinks:
        current_root = SELENIUM_CACHE / "current"
        if current_root.is_symlink() or current_root.exists():
            try:
                current_root.unlink()
            except IsADirectoryError:
                shutil.rmtree(current_root)
        current_root.symlink_to(version_root, target_is_directory=True)

        return str(chrome_binary), str(chromedriver_binary)


def create_driver():
    chrome_binary, driver_binary = ensure_latest_chrome_runtime()

    chrome_options = Options()
    chrome_options.binary_location = chrome_binary
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1280,1000")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.6099.71 Safari/537.36"
    )

    service = Service(driver_binary)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver