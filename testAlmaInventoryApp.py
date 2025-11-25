#!/usr/bin/env python3
"""
Chromium-compatible Selenium script.
Fully handles jQuery UI barcode dialog workflow.

Flow:
 1. Detect local Chromium version
 2. Download matching ChromeDriver from Google's "chrome-for-testing" API
 3. Open barcodeReport.html
 4. Close initial "Add Barcode" dialog
 5. Wait until library dropdown (#libSelected) populated (must contain "Animal Hospital")
 6. Reopen Add Barcode dialog via toolbar link (#addb)
 7. Type barcode and submit
 8. Wait for result row with non-empty .status
 9. Print CSV row to stdout
"""

import argparse
import csv
import io
import json
import os
import sys
import tempfile
import time
import urllib.request
import zipfile
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


# ---------- Utility functions ----------

def get_chromium_version(binary="/usr/bin/chromium-browser"):
    """Return the local Chromium version string."""
    try:
        out = subprocess.check_output([binary, "--version"]).decode()
        return out.strip().split()[1]
    except Exception as e:
        raise RuntimeError(f"Failed to get Chromium version from {binary}: {e}")


def download_matching_chromedriver(version):
    """Download the correct ChromeDriver matching a Chromium version."""
    major = version.split(".")[0]
    api = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
    print(f"Fetching ChromeDriver list from {api} ...", file=sys.stderr)

    data = json.load(urllib.request.urlopen(api))
    match = None
    for v in data["versions"]:
        if v["version"].startswith(major + "."):
            match = v
            break
    if not match:
        raise RuntimeError(f"No matching ChromeDriver found for Chromium {version}")

    url = next(d["url"] for d in match["downloads"]["chromedriver"] if d["platform"] == "linux64")
    print(f"Downloading ChromeDriver for Chromium {version} ({url}) ...", file=sys.stderr)

    zdata = urllib.request.urlopen(url).read()
    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
        zf.extractall(tmpdir)

    for root, _, files in os.walk(tmpdir):
        if "chromedriver" in files:
            path = os.path.join(root, "chromedriver")
            os.chmod(path, 0o755)
            print(f"Using ChromeDriver binary: {path}", file=sys.stderr)
            return path
    raise RuntimeError("Driver binary not found after extraction.")


def wait_for_dropdown(driver, timeout=30):
    """Wait for #libSelected to populate and contain 'Animal Hospital'."""
    print("Checking #libSelected dropdown...", file=sys.stderr)
    wait = WebDriverWait(driver, timeout)
    select_el = wait.until(EC.presence_of_element_located((By.ID, "libSelected")))

    start = time.time()
    while time.time() - start < 10:
        options = [o.text.strip() for o in select_el.find_elements(By.TAG_NAME, "option") if o.text.strip()]
        if len(options) > 1 and any("Animal Hospital" in o for o in options):
            print(f"✓ Dropdown validated ({len(options)} options, includes 'Animal Hospital').", file=sys.stderr)
            return
        time.sleep(1)
    raise RuntimeError(f"Dropdown not populated or 'Animal Hospital' missing: {options[:5]}...")


def wait_for_status(driver, barcode, timeout=180):
    """Wait for the table row for the given barcode to have a non-empty .status cell."""
    row_selector = f'tr.datarow[barcode="{barcode}"]'
    wait = WebDriverWait(driver, timeout)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, row_selector)))

    start = time.time()
    while time.time() - start < timeout:
        row = driver.find_element(By.CSS_SELECTOR, row_selector)
        status_cell = row.find_element(By.CSS_SELECTOR, "td.status")
        if status_cell.text.strip():
            return row
        time.sleep(1)
    raise RuntimeError("Timed out waiting for status cell to populate.")


# ---------- Main workflow ----------

def run_barcode(url, barcode):
    # --- Detect and fetch matching ChromeDriver ---
    chromium_binary = "/usr/bin/chromium-browser"  # adjust if needed
    version = get_chromium_version(chromium_binary)
    driver_path = download_matching_chromedriver(version)

    # --- Configure Chrome options ---
    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1400,1000")
    chrome_opts.binary_location = chromium_binary

    driver = webdriver.Chrome(service=Service(driver_path), options=chrome_opts)

    try:
        print(f"Opening {url} ...", file=sys.stderr)
        driver.get(url)

        # 1. Close initial Add Barcode dialog if present
        print("Checking if initial 'Add Barcode' dialog is open...", file=sys.stderr)
        try:
            dialog = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.ID, "dialog-form"))
            )
            # The dialog close button is typically a span[role=button] inside .ui-dialog-titlebar
            close_button = driver.find_element(By.CSS_SELECTOR, ".ui-dialog-titlebar-close")
            close_button.click()
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ui-widget-overlay"))
            )
            print("✓ Closed initial barcode dialog.", file=sys.stderr)
        except Exception:
            print("No initial dialog visible or already closed.", file=sys.stderr)

        # 2. Validate dropdown
        wait_for_dropdown(driver)

        # 3. Reopen Add Barcode dialog
        print("Reopening Add Barcode dialog...", file=sys.stderr)
        addb = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "addb")))
        driver.execute_script("arguments[0].scrollIntoView(true);", addb)
        time.sleep(0.5)
        addb.click()

        # Wait for dialog to open
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.ID, "dialog-form")))
        print("✓ Barcode dialog reopened.", file=sys.stderr)

        # 4. Fill in barcode
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "barcode")))
        barcode_input = driver.find_element(By.ID, "barcode")
        barcode_input.clear()
        barcode_input.send_keys(barcode)
        barcode_input.send_keys(Keys.ENTER)

        # 5. Click "Add Barcode" button in dialog if visible
        try:
            add_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".ui-dialog-buttonpane .ui-button:not([disabled])"))
            )
            add_button.click()
        except Exception:
            pass

        # 6. Wait for row + status
        row = wait_for_status(driver, barcode)

        # 7. Extract data
        def pick(cls):
            el = row.find_elements(By.CSS_SELECTOR, f"td.{cls}")
            return el[0].text.strip() if el else ""

        data = {
            "barcode": row.get_attribute("barcode") or "",
            "location_code": pick("location_code"),
            "call_number": pick("call_number"),
            "volume": pick("volume"),
            "title": pick("title"),
            "process": pick("process"),
            "temp_location": pick("temp_location"),
            "bib_supp": pick("bib_supp"),
            "hold_supp": pick("hold_supp"),
            "record_num": pick("record_num"),
            "status": pick("status"),
            "status_msg": pick("status_msg"),
            "timestamp": pick("timestamp"),
        }

        # 8. Output CSV
        writer = csv.DictWriter(sys.stdout, fieldnames=data.keys())
        writer.writeheader()
        writer.writerow(data)

    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Submit barcode and scrape results using Selenium + dynamic ChromeDriver.")
    parser.add_argument("--url", required=True, help="Full URL to barcodeReport.html page")
    parser.add_argument("--barcode", required=True, help="Barcode to submit")
    args = parser.parse_args()

    try:
        run_barcode(args.url, args.barcode)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

