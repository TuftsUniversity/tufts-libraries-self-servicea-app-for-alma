import io
import time
from urllib.parse import quote_plus
from typing import Dict, List
import platform
import shutil
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)
import re

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
class SearchCriterion:
    """
    Scrape Criterion USA College Campus Films search results.

    Flow:
      - Open the College Campus Films page.
      - Fill the search input (name='searchword') with the user title.
      - Click the search button (input[type=image].button[src*='searchButton']).
      - In the results, find all <span class="dy_cat_poster_title">.
      - Keep only spans whose text contains the user title (simple substring, case-insensitive).
      - For each match, follow the parent <a> href to the detail page.
      - On the detail page:
          * Get the film title from <span class="dy_cat_long_ftitle"> (or child <a>).
          * Get key/value fields from table rows like:
            <td class="dy_cat_label_col">Year</td>
            <td class="dy_cat_full_desc_col" colspan="3">2023</td>
      - Build a DataFrame, drop exact duplicate rows, and return an XLSX buffer.
    """

    BASE_URL = "https://www.criterionpicusa.com/our-markets/college-campus-films"

    def __init__(
        self,
        film_title: str,

    ):
        self.title = (film_title or "").strip()


    # ---------- logging helpers ----------

    def log(self, msg: str) -> None:
  
        print(f"[CRITERION DEBUG] {msg}", flush=True)

    # ---------- driver helper ----------


    def create_driver(self):

        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/chromium-browser"

        # NEW HEADLESS MODE — required for Angular/Javascript-heavy sites.
        chrome_options.add_argument("--headless=new")

        # User agent spoof (critical for Swank rendering)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.6099.71 Safari/537.36"
        )

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1280,1000")
        chrome_options.add_argument("--enable-javascript")

        # Path to correct chromedriver (as we fixed earlier)
        driver_path = "/usr/local/bin/chromedriver"

        self.log(f"Launching Chromium via: {driver_path}")

        driver = webdriver.Chrome(
            executable_path=driver_path,
            chrome_options=chrome_options
        )
        driver.set_page_load_timeout(60)
        return driver
    # ---------- text helpers ----------

    @staticmethod
    def _normalize_for_match(s: str) -> str:
        """Normalize text for substring matching (case-insensitive, collapse whitespace)."""
        if s is None:
            return ""
        s = s.lower()
        s = re.sub(r"\s+", "", s)
        return s

    def _title_matches(self, candidate_text: str) -> bool:
        """
        Return True if the user-provided title appears (as a substring)
        in the candidate text, after simple normalization.
        """
        user_norm = self._normalize_for_match(self.title)
        cand_norm = self._normalize_for_match(candidate_text)
        if not user_norm or not cand_norm:
            return False
        return user_norm in cand_norm

    # ---------- core scraping ----------

    def _perform_search(self, driver: webdriver.Chrome, wait: WebDriverWait) -> None:
        """Load the page, enter the title, and click the search button."""
        self.log(f"Navigating to Criterion base URL: {self.BASE_URL}")
        driver.get(self.BASE_URL)

        import urllib.parse

        
        term = urllib.parse.quote_plus(self.title)

        

        driver.get(f"https://media3.criterionpic.com/htbin/wwform/014/wwt770?kw={term}&x=0&y=0&task=search&ad=AndPlusOr&option=com_search&Itemid=101")
       

    def _collect_matching_result_links(
        self, driver: webdriver.Chrome, wait: WebDriverWait
    ) -> List[str]:
        """
        On the results page, find all spans with class 'dy_cat_poster_title'.
        Keep only those whose text contains the user title, and return their
        parent <a> hrefs.
        """
        try:
            wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "span.dy_cat_poster_title")
                )
            )
        except TimeoutException:
            self.log("❌ No spans with class dy_cat_poster_title found; no matching films.")
            return []

        spans = driver.find_elements(By.CSS_SELECTOR, "span.dy_cat_poster_title")
        self.log(f"Found {len(spans)} dy_cat_poster_title spans in results.")

        hrefs: List[str] = []
        for span in spans:
            text = (span.text or "").strip()
            if not text:
                continue
            if not self._title_matches(text):
                # e.g. "Devil's Men (2023)" won't match "12 Angry Men"
                continue

            try:
                link_el = span.find_element(By.XPATH, "./ancestor::a[1]")
                href = link_el.get_attribute("href")
                if href and href not in hrefs:
                    hrefs.append(href)
                    self.log(f"Matched title: {text!r} -> {href}")
            except NoSuchElementException:
                self.log(f"⚠ Span {text!r} had no ancestor <a>; skipping.")

        self.log(f"{len(hrefs)} Criterion detail URLs matched the user title.")
        return hrefs

    def _scrape_film_detail(
        self, driver: webdriver.Chrome, wait: WebDriverWait
    ) -> Dict[str, str]:
        """
        On a Criterion detail page, extract:
          - Title (from span.dy_cat_long_ftitle, or child <a>)
          - Key/value rows from td.dy_cat_label_col / td.dy_cat_full_desc_col
          - Detail Page URL
        """
        data: Dict[str, str] = {}

        # Title
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "span.dy_cat_long_ftitle")
                )
            )
        except TimeoutException:
            self.log("❌ Timeout waiting for span.dy_cat_long_ftitle on detail page.")
            return {}

        try:
            title_container = driver.find_element(
                By.CSS_SELECTOR, "span.dy_cat_long_ftitle"
            )
            try:
                title_el = title_container.find_element(By.TAG_NAME, "a")
            except NoSuchElementException:
                title_el = title_container
            title_text = (title_el.text or "").strip()
        except NoSuchElementException:
            title_text = ""

        if title_text:
            data["Title"] = title_text
            self.log(f"Detail page Title: {title_text!r}")
        else:
            self.log("⚠ No Title text found on detail page.")

        # Always record the page URL
        data["Detail Page URL"] = driver.current_url

        # Fields from label/value table rows
        label_cells = driver.find_elements(By.CSS_SELECTOR, "td.dy_cat_label_col")
        self.log(f"Found {len(label_cells)} td.dy_cat_label_col cells.")

        for label_td in label_cells:
            label = (label_td.text or "").strip().rstrip(":")
            if not label:
                continue
            try:
                value_td = label_td.find_element(
                    By.XPATH, "following-sibling::td[@class='dy_cat_full_desc_col'][1]"
                )
            except NoSuchElementException:
                self.log(f"⚠ No dy_cat_full_desc_col sibling for label {label!r}")
                continue
            value = (value_td.text or "").strip()
            data[label] = value
            self.log(f"  {label}: {value}")

        return data

    # ---------- DataFrame / Excel ----------

    def _safe_title_for_filename(self) -> str:
        """Sanitize the title for use in a filename."""
        base = self.title or "results"
        base = base.strip()
        base = re.sub(r"\s+", "_", base)
        base = re.sub(r"[^A-Za-z0-9_\-]", "", base)
        return base or "results"

    def _build_dataframe(self, films: List[Dict[str, str]]) -> pd.DataFrame:
        """Turn list of dicts into a de-duplicated DataFrame with consistent columns."""
        if not films:
            self.log("[DEBUG] _build_dataframe called with empty list; returning empty DataFrame.")
            cols = ["Title", "Detail Page URL"]
            return pd.DataFrame(columns=cols)

        # Union of all keys; ensure Title and Detail Page URL come first if present
        all_keys = set()
        for film in films:
            all_keys.update(film.keys())

        cols = []
        for preferred in ["Title", "Detail Page URL"]:
            if preferred in all_keys:
                cols.append(preferred)
                all_keys.remove(preferred)
        cols.extend(sorted(all_keys))

        df = pd.DataFrame(films, columns=cols)
        # Drop exact duplicate rows to avoid repeats
        before = len(df)
        df = df.drop_duplicates()
        after = len(df)
        if after < before:
            self.log(f"[DEBUG] Removed {before - after} duplicate rows from Criterion DataFrame.")
        return df

    # ---------- public entry point ----------

    def process(self):
        """
        Main entrypoint: run the whole search + scrape + Excel build,
        and return (BytesIO, filename).
        """
        self.log("=== SearchCriterion START ===")
        driver = self.create_driver()
        films: List[Dict[str, str]] = []

        try:
            wait = WebDriverWait(driver, 30)
            self._perform_search(driver, wait)
            hrefs = self._collect_matching_result_links(driver, wait)

            for idx, href in enumerate(hrefs, start=1):
                self.log(f"Fetching Criterion detail {idx}/{len(hrefs)}: {href}")
                driver.get(href)
                film_data = self._scrape_film_detail(driver, wait)
                if film_data:
                    films.append(film_data)

            df = self._build_dataframe(films)

            # Write to in-memory Excel
            buffer = io.BytesIO()
            safe_title = self._safe_title_for_filename()
            filename = f"Criterion_{safe_title}_results.xlsx"

            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Criterion Results", index=False)

            buffer.seek(0)
            self.log(f"=== SearchCriterion COMPLETE. Rows: {len(df)} ===")
            return buffer, filename

        finally:
            try:
                driver.quit()
            except Exception:
                pass
