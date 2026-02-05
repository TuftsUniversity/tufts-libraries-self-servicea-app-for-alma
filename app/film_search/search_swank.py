import io
import time
from urllib.parse import quote_plus
from typing import Dict, List

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SwankSearch:
    """
    Short, reliable Swank film scraper.
    Uses direct search URL:
    https://www.swank.com/college-campus/Search?query={}&license=college_campus
    """

    def __init__(self, film_title: str, debug: bool = True):
        self.film_title = film_title.strip()
        self.debug = debug

    # -------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------
    def log(self, msg: str):
        if self.debug:
            print(f"[SWANK DEBUG] {msg}", flush=True)

    def short_html_preview(self, driver, label: str, length: int = 1500):
        try:
            src = driver.page_source
            #self.log(f"--- {label} HTML PREVIEW ---")
            #self.log(src[:length].replace("\n", " ") + " ... [truncated]")
            #self.log("--- END PREVIEW ---")
        except Exception as e:
            self.log(f"HTML preview failed: {e}")

    # -------------------------------------------------------------
    # DRIVER
    # -------------------------------------------------------------
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

        #self.log(f"Launching Chromium via: {driver_path}")

        driver = webdriver.Chrome(
            executable_path=driver_path,
            chrome_options=chrome_options
        )
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

        #self.log(f"Navigating directly to:\n  {url}")
        driver.get(url)
        time.sleep(4)

        #(f"Loaded URL: {driver.current_url}")
        #self.short_html_preview(driver, "SEARCH PAGE")

    # -------------------------------------------------------------
    # SCRAPE SEARCH RESULTS PAGE
    # -------------------------------------------------------------
    def scrape_results(self, driver, wait) -> List[Dict]:

        #self.log("Looking for film carousel...")
        try:
            container = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.carousel-holder.carousel-holder-posters")
                )
            )
        except:
            self.log("❌ No carousel found — no results returned by Swank.")
            return []

        # Get all title nodes and filter by matching film title
        title_nodes = container.find_elements(By.CSS_SELECTOR, "h2")
        matches = []
        for node in title_nodes:
            title_text = node.text.strip()
            if not title_text:
                continue
            if title_text.lower() != self.film_title.lower():
                continue

            # Found a matching title; now get the associated link
            href = None
            try:
                # Get the parent carousel item and find the link within it
                carousel_item = node.find_element(
                    By.XPATH, "./ancestor::div[contains(@class,'panel-carousel-subitem')][1]"
                )
                link_elem = carousel_item.find_element(
                    By.XPATH,
                    ".//div[contains(@class,'panel-carousel-image-holder')]/a[contains(@href,'/details/')]"
                )
                href = link_elem.get_attribute("href")
            except Exception:
                try:
                    # Fallback: use JavaScript to find closest link
                    href = driver.execute_script(
                        "return arguments[0].closest('.panel-carousel-subitem') && "
                        "arguments[0].closest('.panel-carousel-subitem').querySelector('a[href*=\"/details/\"]') && "
                        "arguments[0].closest('.panel-carousel-subitem').querySelector('a[href*=\"/details/\"]').href;",
                        node,
                    )
                except Exception:
                    href = None

            if href:
                matches.append(href)

        self.log(f"Found {len(matches)} matching film link(s).")

        films = []
        main_tab = driver.current_window_handle

        for idx, href in enumerate(matches, start=1):
            if idx > 8:
                break
           # self.log(f"[Film {idx}] href: {href}")

            # open detail page in a new tab
            driver.execute_script("window.open(arguments[0], '_blank');", href)
            time.sleep(1)
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(2)

            films.append(self.scrape_detail_page(driver, wait))

            # Close tab and return
            driver.close()
            driver.switch_to.window(main_tab)
            time.sleep(1)

        return films

    # -------------------------------------------------------------
    # SCRAPE FILM DETAIL PAGE
    # -------------------------------------------------------------
    def scrape_detail_page(self, driver, wait):
        #self.log("Scraping film detail page…")
        url = driver.current_url

        # Store detail URL first
        data = {"Detail Page URL": url}

        # The detail block
        try:
            film_info = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.film-info"))
            )
        except:
            self.log("❌ film-info not found; cannot extract details.")
      

        # Get ALL elements in document order (DOM depth-first)
        all_nodes = film_info.find_elements(By.XPATH, ".//*")

        # Extract all h2 and p nodes in order
        h2_nodes = []
        p_nodes  = []

        for el in all_nodes:
            tag = el.tag_name.lower()
            if tag == "h2":
                h2_nodes.append(el)
            elif tag == "p":
                p_nodes.append(el)

        #self.log(f"[DEBUG] Found {len(h2_nodes)} H2s and {len(p_nodes)} Ps inside film-info.")

        # Capture the visible film title <h1>
        try:
            h1 = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
            )
            film_title = h1.text.strip()
            data["Film Title"] = film_title
           # self.log(f"[DEBUG] Film Title detected: {film_title}")
        except:
            self.log("[DEBUG] No <h1> film title found on detail page.")
            data["Film Title"] = ""

        # Function to compute dom index
        node_to_index = {el: i for i, el in enumerate(all_nodes)}

        # Pair each h2 with the nearest following p
        for h2 in h2_nodes:
            h2_index = node_to_index[h2]
            h2_text  = h2.text.strip()
            if not h2_text:
                continue

            # Find the first <p> AFTER this <h2>
            following_ps = [p for p in p_nodes if node_to_index[p] > h2_index]

            if not following_ps:
                continue

            nearest_p = following_ps[0]
            p_text = nearest_p.text.strip()

            if p_text:
                #self.log(f"[PAIR] {h2_text} = {p_text}")
                data[h2_text] = p_text

        if len(data) <= 1:
            self.log("[WARNING] No H2→P pairs found using linear DOM scan.")

        return data


    def build_dataframe(self, films: List[Dict]) -> pd.DataFrame:
       # self.log(f"[DEBUG] build_dataframe called with {len(films)} films.")

        if not films:
            self.log("[DEBUG] No films found. Returning empty DataFrame with placeholder columns.")
            return pd.DataFrame(columns=["Detail Page URL"])

        # 1. Determine column order based on first appearance
        ordered_columns = []
        for film in films:
            for key in film.keys():
                if key not in ordered_columns:
                    ordered_columns.append(key)

        #self.log(f"[DEBUG] Ordered columns = {ordered_columns}")

        # 2. Build rows
        rows = []
        for film in films:
            row = {col: "" for col in ordered_columns}
            for k, v in film.items():
                row[k] = v
            rows.append(row)

        df = pd.DataFrame(rows, columns=ordered_columns)

        # 3. Dedup rows
        before = len(df)
        df = df.drop_duplicates(keep="first").reset_index(drop=True)
        after = len(df)
       # self.log(f"[DEBUG] Dedup removed {before - after} duplicate rows.")

        #self.log("[DEBUG] DataFrame built successfully.")
        return df


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
