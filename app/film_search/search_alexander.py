#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import quote_plus


class AlexanderScraper:
    """
    Full Criterion scraper using ONLY requests + BeautifulSoup.
    Handles:
        - multi-result search pages
        - single-result auto-redirect detail pages
        - detail-page scraping of label/value pairs
    """

    # BASE_SEARCH = (
    #     "https://media3.criterionpic.com/htbin/wwform/014/wwt770"
    #     "?kw={kw}&task=search&ad=AndPlusOr&option=com_search&Itemid=101"
    # )

    # HEADERS = {
    #     "User-Agent": (
    #         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    #         "AppleWebKit/537.36 (KHTML, like Gecko) "
    #         "Chrome/120.0 Safari/537.36"
    #     )
    # }

    def __init__(self, title: str, debug: bool = False):
        self.title = title.strip()
        self.debug = debug
        self.SEARCH_ENDPOINT = f"https://search.alexanderstreet.com/search?searchstring="


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
        url = self.BASE_SEARCH.format(encoded)
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
    # def scrape_detail_page(self, url: str) -> dict:
    #     r = requests.get(url, headers=self.HEADERS, timeout=20)
    #     r.raise_for_status()
    #     soup = BeautifulSoup(r.text, "html.parser")

    #     data = {}
    #     data["Detail Page URL"] = url

    #     # ----- Title -----
    #     title_span = soup.select_one("span.dy_cat_long_ftitle")
    #     if title_span:
    #         a = title_span.find("a")
    #         data["Title"] = a.get_text(strip=True) if a else title_span.get_text(strip=True)
    #     else:
    #         data["Title"] = ""

    #     # ----- Fields (label/value table rows) -----
    #     labels = soup.select("td.dy_cat_label_col")
    #     for lab in labels:
    #         label = lab.get_text(strip=True).rstrip(":")
    #         val_td = lab.find_next("td", class_="dy_cat_full_desc_col")
    #         value = val_td.get_text(strip=True) if val_td else ""
    #         data[label] = value

    #     return data

    def scrape_metadata_from_search(self, soup: BeautifulSoup) -> dict:
        data = []

        container = soup.select_one(".search-result-citation-container")

        for span in container.select("[data-field]"):
            data_dict = {}
            label = span["data-field"]
            value = span.get_text(" ", strip=True)

            if label and value:
                data_dict[label] = value

            data.append(data_dict)


        return data
    # --------------------------------------------------------
    # Main processing
    # --------------------------------------------------------
    def process(self):
        search_url, html = self.perform_search()

        soup = BeautifulSoup(html, "html.parser")

        # Detect if we are have results
        if "search-result-citation-container" in html:
            # single auto-redirect case
            films = self.scrape_metadata_from_search(soup)

            df = pd.DataFrame(films)

        #     df = pd.DataFrame([data])
                    # ---- Convert DataFrame to Excel buffer ----
            buffer = io.BytesIO()
            filename = f"alexander_street_search_results_{self.title.replace(' ', '_')}.xlsx"

            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Alexander Street Press Results")

            buffer.seek(0)   # IMPORTANT: reset pointer before returning

            return buffer, filename
        else:
            return None




