import io
import time
from typing import Dict, List
from urllib.parse import urljoin

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SearchKanopy:
    """
    Selenium scraper for Kanopy search.
    Loads https://www.kanopy.com/en/tufts/search
    Enters a search term and visits matching results.
    """

    SEARCH_URL = "https://www.kanopy.com/en/tufts/search"

    def __init__(self, film_title: str, debug: bool = True):
        self.film_title = film_title.strip()
        self.debug = debug

    # -------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------
    def log(self, msg: str):
        if self.debug:
            print(f"[KANOPY DEBUG] {msg}", flush=True)

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
        driver = webdriver.Chrome(
            executable_path=driver_path,
            chrome_options=chrome_options
        )
        driver.set_page_load_timeout(60)
        return driver

    # -------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------
    def load_search_results(self, driver, wait):
        driver.get(self.SEARCH_URL)

        search_input = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[placeholder="Search"]')
            )
        )
        search_input.clear()
        search_input.send_keys(self.film_title)
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)

    def collect_result_links(self, driver, wait) -> List[str]:
        wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.title"))
        )

        title_nodes = driver.find_elements(By.CSS_SELECTOR, "div.title")
        matches = []
        for node in title_nodes:
            title_text = node.text.strip()
            if not title_text:
                continue
            if title_text.lower() != self.film_title.lower():
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

            if href:
                matches.append(href)

        deduped = []
        for link in matches:
            abs_link = urljoin("https://www.kanopy.com", link)
            if abs_link not in deduped:
                deduped.append(abs_link)

        self.log(f"Found {len(deduped)} matching result link(s).")
        return deduped

    # -------------------------------------------------------------
    # DETAIL PAGE
    # -------------------------------------------------------------
    def scrape_detail_page(self, driver, wait) -> Dict:
        data: Dict[str, str] = {"Detail Page URL": driver.current_url}

        try:
            h3 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h3")))
            data["Film Title"] = h3.text.strip()
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

        info_sections = driver.find_elements(By.CSS_SELECTOR, "h2.info-section-title")
        for h2 in info_sections:
            label = h2.text.strip()
            if not label:
                continue

            values = []
            try:
                container = h2.find_element(By.XPATH, "..")
                links = container.find_elements(By.CSS_SELECTOR, "div.term-info-section-item a")
                values = [a.text.strip() for a in links if a.text.strip()]
            except Exception:
                values = []

            if not values:
                try:
                    container = h2.find_element(
                        By.XPATH, "./ancestor::div[contains(@class,'info-section')][1]"
                    )
                    links = container.find_elements(By.CSS_SELECTOR, "div.term-info-section-item a")
                    values = [a.text.strip() for a in links if a.text.strip()]
                except Exception:
                    values = []

            if values:
                data[label] = "; ".join(values)
            else:
                data[label] = ""

        return data

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

            films = []
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

    def build_dataframe(self, films: List[Dict]) -> pd.DataFrame:
        if not films:
            return pd.DataFrame(columns=["Detail Page URL"])

        ordered_columns = []
        for film in films:
            for key in film.keys():
                if key not in ordered_columns:
                    ordered_columns.append(key)

        rows = []
        for film in films:
            row = {col: "" for col in ordered_columns}
            for k, v in film.items():
                row[k] = v
            rows.append(row)

        df = pd.DataFrame(rows, columns=ordered_columns)
        df = df.drop_duplicates(keep="first").reset_index(drop=True)
        return df
