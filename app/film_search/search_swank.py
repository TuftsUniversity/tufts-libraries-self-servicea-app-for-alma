import io
import time
from urllib.parse import quote_plus
from typing import Dict, List, Tuple

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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


class SwankSearch(_TitleScorerMixin):
    """
    Swank film scraper.
    Uses direct search URL:
    https://www.swank.com/college-campus/Search?query={}&license=college_campus

    Updated:
      - Uses title scoring instead of exact title equality.
      - Filters to strong matches (score>=2) if any exist; otherwise keeps score>0; otherwise keeps all.
    """

    def __init__(self, film_title: str, debug: bool = True, max_results: int = 25):
        self.film_title = (film_title or "").strip()
        self.debug = debug
        self.max_results = max_results

    # -------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------
    def log(self, msg: str):
        if self.debug:
            print(f"[SWANK] {msg}", flush=True)

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
    # DIRECT SEARCH URL LOAD
    # -------------------------------------------------------------
    def load_search_results(self, driver):
        encoded = quote_plus(self.film_title)
        url = (
            f"https://www.swank.com/college-campus/Search"
            f"?query={encoded}"
            f"&license=college_campus"
        )
        driver.get(url)
        time.sleep(4)

    # -------------------------------------------------------------
    # SCRAPE SEARCH RESULTS PAGE
    # -------------------------------------------------------------
    def scrape_results(self, driver, wait) -> List[Dict]:
        try:
            container = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.carousel-holder.carousel-holder-posters")
                )
            )
        except Exception:
            self.log("No carousel found — no results returned by Swank.")
            return []

        film_links = container.find_elements(
            By.XPATH,
            ".//div[contains(@class,'panel-carousel-image-holder') "
            "and not(contains(@class,'slick-cloned'))]"
            "/a[contains(@href,'/details/')]"
        )

        self.log(f"Found {len(film_links)} film link(s).")

        films = []
        main_tab = driver.current_window_handle

        for idx, link in enumerate(film_links, start=1):
            if idx > self.max_results:
                break

            href = link.get_attribute("href")
            if not href:
                continue

            driver.execute_script("window.open(arguments[0], '_blank');", href)
            time.sleep(1)
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(2)

            films.append(self.scrape_detail_page(driver, wait))

            driver.close()
            driver.switch_to.window(main_tab)
            time.sleep(1)

        return films

    # -------------------------------------------------------------
    # SCRAPE FILM DETAIL PAGE
    # -------------------------------------------------------------
    def scrape_detail_page(self, driver, wait):
        url = driver.current_url
        data = {"Detail Page URL": url}

        # film title is in <h1> on Swank
        try:
            h1 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")))
            data["Film Title"] = (h1.text or "").strip()
        except Exception:
            data["Film Title"] = ""

        # Detail block
        try:
            film_info = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.film-info")))
        except Exception:
            return data

        all_nodes = film_info.find_elements(By.XPATH, ".//*")

        h2_nodes = []
        p_nodes = []
        for el in all_nodes:
            tag = (el.tag_name or "").lower()
            if tag == "h2":
                h2_nodes.append(el)
            elif tag == "p":
                p_nodes.append(el)

        node_to_index = {el: i for i, el in enumerate(all_nodes)}

        for h2 in h2_nodes:
            h2_index = node_to_index.get(h2, -1)
            label = (h2.text or "").strip()
            if not label:
                continue

            following_ps = [p for p in p_nodes if node_to_index.get(p, -1) > h2_index]
            if not following_ps:
                continue
            value = (following_ps[0].text or "").strip()
            if value:
                data[label] = value

        return data

    def build_dataframe(self, films: List[Dict]) -> pd.DataFrame:
        if not films:
            return pd.DataFrame(columns=["Detail Page URL", "Film Title"])

        # Column order based on first appearance
        ordered_columns = []
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

        # Title-score filter
        if not df.empty and "Film Title" in df.columns:
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
        self.log(f"=== SwankSearch START for '{self.film_title}' ===")

        driver = None
        try:
            driver = self.create_driver()
            wait = WebDriverWait(driver, 20)

            self.load_search_results(driver)

            films = self.scrape_results(driver, wait)
            df = self.build_dataframe(films)

            output = io.BytesIO()
            df.to_excel(output, index=False, engine="openpyxl")
            output.seek(0)

            safe = self.film_title.replace(" ", "_")
            filename = f"Swank_{safe}_results.xlsx"

            self.log(f"=== SwankSearch COMPLETE. Rows: {len(df)} ===")
            return output, filename

        finally:
            if driver:
                driver.quit()