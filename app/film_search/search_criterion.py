# criterion_scraper_no_selenium.py
import io
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import quote_plus


class SearchCriterion:
    """
    Full Criterion scraper using ONLY requests + BeautifulSoup.
    Handles:
        - multi-result search pages
        - single-result auto-redirect detail pages
        - detail-page scraping of label/value pairs
    """

    BASE_SEARCH = (
        "https://media3.criterionpic.com/htbin/wwform/014/wwt770"
        "?kw={kw}&task=search&ad=AndPlusOr&option=com_search&Itemid=101"
    )

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    def __init__(self, film_title: str):
        self.title = film_title.strip()

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    def _normalize(self, s: str) -> str:
        if not s:
            return ""
        return re.sub(r"\s+", "", s.lower())

    def _title_match(self, a, user_norm: str) -> bool:
        text = a.get_text(strip=True)
        return user_norm in self._normalize(text)

    # --------------------------------------------------------
    # Search handling
    # --------------------------------------------------------
    def perform_search(self):
        encoded = quote_plus(self.title)
        url = self.BASE_SEARCH.format(kw=encoded)
        r = requests.get(url, headers=self.HEADERS, timeout=20)
        r.raise_for_status()
        return url, r.text

    # --------------------------------------------------------
    # Parse list page
    # --------------------------------------------------------
    def extract_list_page_links(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        user_norm = self._normalize(self.title)

        spans = soup.select("span.dy_cat_poster_title")
        links = []

        for span in spans:
            a = span.find_parent("a")
            if not a:
                continue

            if self._title_match(a, user_norm):
                href = a.get("href")
                if href and href.startswith("/"):
                    href = "https://media3.criterionpic.com" + href
                links.append(href)

        return links

    # --------------------------------------------------------
    # Parse detail page
    # --------------------------------------------------------
    def scrape_detail_page(self, url: str) -> dict:
        r = requests.get(url, headers=self.HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        data = {}
        data["Detail Page URL"] = url

        # ----- Title -----
        title_span = soup.select_one("span.dy_cat_long_ftitle")
        if title_span:
            a = title_span.find("a")
            data["Title"] = a.get_text(strip=True) if a else title_span.get_text(strip=True)
        else:
            data["Title"] = ""

        # ----- Fields (label/value table rows) -----
        labels = soup.select("td.dy_cat_label_col")
        for lab in labels:
            label = lab.get_text(strip=True).rstrip(":")
            val_td = lab.find_next("td", class_="dy_cat_full_desc_col")
            value = val_td.get_text(strip=True) if val_td else ""
            data[label] = value

        return data

    # --------------------------------------------------------
    # Main processing
    # --------------------------------------------------------
    def process(self):
        search_url, html = self.perform_search()

        # Detect if we are already on a detail page
        if "dy_cat_long_ftitle" in html:
            # single auto-redirect case
            data = self.scrape_detail_page(search_url)
            df = pd.DataFrame([data])
        else:
            links = self.extract_list_page_links(html)

            # If zero results: return empty Excel file
            if not links:
                df = pd.DataFrame([])
            else:
                films = []
                for href in links:
                    films.append(self.scrape_detail_page(href))
                df = pd.DataFrame(films)

        # ---- Convert DataFrame to Excel buffer ----
        buffer = io.BytesIO()
        filename = f"criterion_search_results_{self.title.replace(' ', '_')}.xlsx"

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Criterion Results")

        buffer.seek(0)   # IMPORTANT: reset pointer before returning

        return buffer, filename
