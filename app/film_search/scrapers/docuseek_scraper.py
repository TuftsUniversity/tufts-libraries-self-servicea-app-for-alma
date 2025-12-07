# app/film_search/scrapers/docuseek_scraper.py

import io
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict


class DocuseekScraper:
    """
    Standalone Docuseek scraper.
    Accepts:
        - A full Docuseek URL (list, search, or detail page)
    Produces:
        - Excel buffer + filename
    """

    BASE = "https://docuseek2.com"

    def __init__(self, url: str, debug: bool = False):
        self.url = url.strip()
        self.debug = debug

    def log(self, msg: str):
        if self.debug:
            print(f"[DOCUSEEK] {msg}", flush=True)

    # -----------------------------------
    # Fetch helper
    # -----------------------------------
    def _fetch_soup(self, url: str) -> BeautifulSoup:
        self.log(f"Fetching: {url}")
        r = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    " AppleWebKit/537.36 (KHTML, like Gecko)"
                    " Chrome/122.0 Safari/537.36"
                )
            },
            timeout=20,
        )
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    # -----------------------------------
    # Identify if a page is a detail page
    # -----------------------------------
    def _is_detail_page(self, soup: BeautifulSoup) -> bool:
        return bool(soup.select_one("#film-detail-wrapper"))

    # -----------------------------------
    # Scrape film detail page
    # -----------------------------------
    def _scrape_detail(self, url: str) -> Dict[str, str]:
        soup = self._fetch_soup(url)
        data = {"Detail Page URL": url}

        # Title
        h1 = soup.select_one("h1.title") or soup.select_one("h1")
        data["Title"] = h1.get_text(strip=True) if h1 else ""

        # Description
        desc = soup.select_one(".film-description")
        data["Description"] = desc.get_text(strip=True) if desc else ""

        # Metadata rows:
        for row in soup.select(".film-info .film-info-row"):
            lab = row.select_one(".film-info-label")
            val = row.select_one(".film-info-value")
            if lab and val:
                key = lab.get_text(strip=True).rstrip(":")
                data[key] = val.get_text(" ", strip=True)

        return data

    # -----------------------------------
    # Extract detail URLs from list page
    # -----------------------------------
    def _extract_detail_urls(self, soup: BeautifulSoup) -> List[str]:
        urls = set()

        for a in soup.select("a[href]"):
            href = a["href"]
            # Typical detail slugs look like "/gs-tu" or "/hmns"
            if href.startswith("/") and len(href) > 1 and "-" in href:
                urls.add(self.BASE + href)

        urls = sorted(urls)
        self.log(f"Found {len(urls)} detail links.")
        return urls

    # -----------------------------------
    # MAIN SCRAPER
    # -----------------------------------
    def scrape(self) -> pd.DataFrame:
        soup = self._fetch_soup(self.url)

        # Detail page
        if self._is_detail_page(soup):
            self.log("Detected DETAIL PAGE")
            row = self._scrape_detail(self.url)
            return pd.DataFrame([row])

        # Otherwise treat as list page
        self.log("Detected LIST PAGE")
        detail_urls = self._extract_detail_urls(soup)

        rows = [self._scrape_detail(u) for u in detail_urls]
        return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)

    # -----------------------------------
    # RETURN EXCEL BUFFER
    # -----------------------------------
    def process(self):
        df = self.scrape()

        buffer = io.BytesIO()
        safe = re.sub(r"[^A-Za-z0-9_\-]", "", self.url.replace(" ", "_")) or "docuseek"
        filename = f"docuseek_results_{safe}.xlsx"

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Docuseek Results")

        buffer.seek(0)
        return buffer, filename
