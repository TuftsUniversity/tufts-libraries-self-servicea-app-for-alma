# search_kanopy.py
import io
import time
from typing import Dict, List, Tuple
from urllib.parse import urljoin

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import re
from typing import Optional

class _TitleScorerMixin:
    @staticmethod
    def _norm_spaces(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "")).strip()

    @staticmethod
    def _norm_compact(s: str) -> str:
        # Ignore punctuation/spaces for "compact" match
        return re.sub(r"\W+", "", (s or "").lower())

    def _title_score(self, candidate: str, want: Optional[str] = None) -> int:
        """
        3 = exact compact match (ignore punctuation)
        2 = exact normalized match (spaces collapsed, case-insensitive)
        1 = contains (want in candidate)
        0 = no match

        NOTE: This is intentionally simple (deterministic, no difflib).
        """
        want = (want if want is not None else getattr(self, "title", "") or getattr(self, "film_title", "") or "").strip()
        cand = (candidate or "").strip()
        if not want or not cand:
            return 0

        want_comp = self._norm_compact(want)
        cand_comp = self._norm_compact(cand)
        if want_comp and cand_comp == want_comp:
            return 3

        want_norm = self._norm_spaces(want).lower()
        cand_norm = self._norm_spaces(cand).lower()
        if want_norm and cand_norm == want_norm:
            return 2

        if want_norm and want_norm in cand_norm:
            return 1

        return 0


class SearchKanopy(_TitleScorerMixin):
    """
    Selenium scraper for Kanopy search.
    Loads https://www.kanopy.com/en/tufts/search
    Enters a search term and visits matching results.

    Updated:
      - Uses title scoring instead of exact title equality.
      - Filters to strong matches (score>=2) if any exist; otherwise keeps score>0; otherwise keeps all.
    """

    SEARCH_URL = "https://www.kanopy.com/en/tufts/search"

    def __init__(self, film_title: str, debug: bool = True, max_results: int = 25):
        self.film_title = (film_title or "").strip()
        self.debug = debug
        self.max_results = max_results

    def log(self, msg: str):
        if self.debug:
            print(f"[KANOPY] {msg}", flush=True)

    # -------------------------------------------------------------
    # DRIVER
    # -------------------------------------------------------------
    def create_driver(self):
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/chromium-browser"

        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.6099.71 Safari/537.36"
        )
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1280,1000")
        chrome_options.add_argument("--enable-javascript")

        driver_path = "/usr/local/bin/chromedriver"
        driver = webdriver.Chrome(executable_path=driver_path, chrome_options=chrome_options)
        driver.set_page_load_timeout(60)
        return driver

    # -------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------
    def load_search_results(self, driver, wait):
        driver.get(self.SEARCH_URL)

        search_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Search"]'))
        )
        search_input.clear()
        search_input.send_keys(self.film_title)
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)

    def collect_result_links(self, driver, wait) -> List[str]:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.title")))

        title_nodes = driver.find_elements(By.CSS_SELECTOR, "div.title")
        hits: List[Tuple[int, str]] = []

        for node in title_nodes:
            title_text = (node.text or "").strip()
            if not title_text:
                continue

            href = None
            try:
                href = node.find_element(By.XPATH, "./ancestor::a[1]").get_attribute("href")
            except Exception:
                try:
                    href = driver.execute_script(
                        "return arguments[0].closest('a') && arguments[0].closest('a').href;",
                        node,
                    )
                except Exception:
                    href = None

            if not href:
                continue

            score = self._title_score(title_text, want=self.film_title)
            if score > 0:
                hits.append((score, href))

        # Prefer strong matches if any exist
        if any(s >= 2 for s, _ in hits):
            hits = [(s, u) for s, u in hits if s >= 2]

        hits.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate, cap
        deduped: List[str] = []
        seen = set()
        for _, link in hits:
            abs_link = urljoin("https://www.kanopy.com", link)
            if abs_link in seen:
                continue
            seen.add(abs_link)
            deduped.append(abs_link)
            if len(deduped) >= self.max_results:
                break

        self.log(f"Selected {len(deduped)} matching result link(s) after title scoring.")
        return deduped

    # -------------------------------------------------------------
    # DETAIL PAGE
    # -------------------------------------------------------------
    def scrape_detail_page(self, driver, wait) -> Dict[str, str]:
        data: Dict[str, str] = {"Detail Page URL": driver.current_url}

        try:
            h3 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h3")))
            data["Film Title"] = (h3.text or "").strip()
        except Exception:
            data["Film Title"] = ""

        try:
            year = driver.find_element(By.CSS_SELECTOR, "div.product-release-year").text.strip()
            data["Release Year"] = year
        except Exception:
            data["Release Year"] = ""

        try:
            duration = driver.find_element(By.CSS_SELECTOR, "div.product-duration").text.strip()
            data["Duration"] = duration
        except Exception:
            data["Duration"] = ""

        # Section header + sibling items
        info_sections = driver.find_elements(By.CSS_SELECTOR, "h2.info-section-title")
        for h2 in info_sections:
            label = (h2.text or "").strip()
            if not label:
                continue

            values: List[str] = []
            try:
                section_container = h2.find_element(
                    By.XPATH, "./ancestor::div[contains(@class,'info-section-container')][1]"
                )
                links = section_container.find_elements(
                    By.CSS_SELECTOR,
                    "div.term-info-section-items div.term-info-section-item a"
                )
                values = [a.text.strip() for a in links if a.text and a.text.strip()]
            except Exception:
                values = []

            data[label] = "; ".join(values) if values else ""

        return data

    # -------------------------------------------------------------
    # DataFrame + filtering
    # -------------------------------------------------------------
    def build_dataframe(self, films: List[Dict[str, str]]) -> pd.DataFrame:
        if not films:
            return pd.DataFrame(columns=["Detail Page URL", "Film Title"])

        # Column order based on first appearance
        ordered_columns: List[str] = []
        for film in films:
            for key in film.keys():
                if key not in ordered_columns:
                    ordered_columns.append(key)

        rows = []
        for film in films:
            row = {col: "" for col in ordered_columns}
            row.update({k: (v if v is not None else "") for k, v in film.items()})
            rows.append(row)

        df = pd.DataFrame(rows, columns=ordered_columns)
        if df.empty:
            return df

        # Title-score filter
        if "Film Title" in df.columns:
            scores = df["Film Title"].fillna("").apply(lambda t: self._title_score(t, want=self.film_title))
            if (scores >= 2).any():
                df = df.loc[scores >= 2].copy()
            elif (scores > 0).any():
                df = df.loc[scores > 0].copy()

        return df.drop_duplicates(keep="first").reset_index(drop=True)

    # -------------------------------------------------------------
    # MAIN PROCESS WRAPPER (for Flask)
    # -------------------------------------------------------------
    def process(self):
        self.log(f"=== SearchKanopy START for '{self.film_title}' ===")

        driver = None
        try:
            driver = self.create_driver()
            wait = WebDriverWait(driver, 20)

            self.load_search_results(driver, wait)
            links = self.collect_result_links(driver, wait)

            films: List[Dict[str, str]] = []
            for href in links:
                driver.get(href)
                time.sleep(2)
                films.append(self.scrape_detail_page(driver, wait))

            df = self.build_dataframe(films)

            output = io.BytesIO()
            df.to_excel(output, index=False, engine="openpyxl")
            output.seek(0)

            safe = self.film_title.replace(" ", "_")
            filename = f"Kanopy_{safe}_results.xlsx"

            self.log(f"=== SearchKanopy COMPLETE. Rows: {len(df)} ===")
            return output, filename

        finally:
            if driver:
                driver.quit()
