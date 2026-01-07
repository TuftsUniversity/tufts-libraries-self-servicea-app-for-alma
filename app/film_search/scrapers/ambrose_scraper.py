import io
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import quote_plus


class AmbroseScraper:
    """
    Scrapes Ambrose Video by title.
    Steps:
      1. Build search URL from title
      2. Parse film result links
      3. Scrape each film detail page
      4. Return Excel buffer + filename
    """

    SEARCH_ENDPOINT = "https://www.ambrosevideo.com/search?search_api_fulltext={}"
    BASE = "https://www.ambrosevideo.com"

    def __init__(self, title: str, debug: bool = False):
        self.title = title.strip()
        self.debug = debug

    def log(self, msg: str):
        if self.debug:
            print(f"[AMBROSE] {msg}", flush=True)

    def _fetch_soup(self, url: str) -> BeautifulSoup:
        self.log(f"Fetching URL: {url}")
        r = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    " AppleWebKit/537.36 (KHTML, like Gecko)"
                    " Chrome/120.0 Safari/537.36"
                )
            },
            timeout=20
        )
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    # ---------------------------------------------------------
    # Build search URL
    # ---------------------------------------------------------
    def _build_search_url(self) -> str:
        return self.SEARCH_ENDPOINT.format(quote_plus(self.title))

    # ---------------------------------------------------------
    # Extract detail URLs from search results
    # ---------------------------------------------------------
    def _extract_detail_urls(self, soup: BeautifulSoup):
        urls = []
        for a in soup.select("a[href^='/video/']"):
            link = self.BASE + a["href"]
            urls.append(link)

        urls = list(dict.fromkeys(urls))
        self.log(f"Found {len(urls)} Ambrose film hits.")
        return urls

    # ---------------------------------------------------------
    # Scrape one film detail page
    # ---------------------------------------------------------
    def _scrape_detail(self, url: str):
        soup = self._fetch_soup(url)
        data = {"Detail Page URL": url}

        # Title
        title_el = soup.select_one("h1.page-title")
        data["Title"] = title_el.get_text(strip=True) if title_el else ""

        # Description
        desc_el = soup.select_one(".field--name-body")
        data["Description"] = desc_el.get_text(" ", strip=True) if desc_el else ""

        # Common metadata fields
        for field in soup.select(".field"):
            label_el = field.select_one(".field__label")
            value_el = field.select_one(".field__item")

            if not label_el or not value_el:
                continue

            label = label_el.get_text(strip=True).rstrip(":")
            value = value_el.get_text(" ", strip=True)

            data[label] = value

        return data

    # ---------------------------------------------------------
    # Build DataFrame
    # ---------------------------------------------------------
    def scrape(self):
        search_url = self._build_search_url()
        soup = self._fetch_soup(search_url)

        detail_urls = self._extract_detail_urls(soup)
        films = [self._scrape_detail(url) for url in detail_urls]

        df = pd.DataFrame(films)

        if not df.empty:
            df = df.drop_duplicates().reset_index(drop=True)

        # Final cleanup: only entries with a real Title
        df = df[(df["Title"].notna()) & (df["Title"] != "")]
        df = df.reset_index(drop=True)

        return df

    # ---------------------------------------------------------
    # Excel Output
    # ---------------------------------------------------------
    def process(self):
        df = self.scrape()

        buffer = io.BytesIO()
        safe = re.sub(r"[^A-Za-z0-9]", "_", self.title) or "ambrose"
        filename = f"ambrose_results_{safe}.xlsx"

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Ambrose Results")

        buffer.seek(0)
        return buffer, filename
