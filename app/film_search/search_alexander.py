#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

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



class AlexanderScraper(_TitleScorerMixin):
    """
    Alexander Street Press search scraper (requests + BeautifulSoup)

    Updated:
      - Uses title scoring instead of exact title equality.
      - Keeps strong matches (score>=2) if any exist; otherwise keeps score>0; otherwise keeps all.
    """

    BASE = "https://search.alexanderstreet.com/"
    SEARCH_URL = "https://search.alexanderstreet.com/search?searchstring={q}"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, title: str, debug: bool = False, max_results: int = 25):
        self.title = (title or "").strip()
        self.debug = debug
        self.max_results = max_results
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def log(self, msg: str) -> None:
        if self.debug:
            print(f"[ALEXANDER] {msg}", flush=True)

    def _get(self, url: str, timeout: int = 30) -> Optional[str]:
        self.log(f"GET {url}")
        try:
            r = self.session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as e:
            self.log(f"GET failed: {e}")
            return None

    # -------------------------
    # Search parsing
    # -------------------------
    def perform_search(self) -> Tuple[str, Optional[str]]:
        q = quote_plus(self.title)
        url = self.SEARCH_URL.format(q=q)
        html = self._get(url)
        return url, html

    def _extract_candidate_links(self, soup: BeautifulSoup) -> List[Tuple[int, str]]:
        """
        Collect likely work/detail links with a score based on anchor text.
        """
        hits: List[Tuple[int, str]] = []
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if not href or href.startswith("#") or "search?" in href:
                continue

            text = a.get_text(" ", strip=True)
            if not text:
                continue

            href_abs = urljoin(self.BASE, href)

            # likely detail pages
            if "/view/" in href:
                score = self._title_score(text)
                if score > 0:
                    hits.append((score, href_abs))

        # sort by score desc, dedupe
        hits.sort(key=lambda x: x[0], reverse=True)
        seen = set()
        out: List[Tuple[int, str]] = []
        for score, u in hits:
            if u in seen:
                continue
            seen.add(u)
            out.append((score, u))
        return out

    def extract_list_page_links(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        hits = self._extract_candidate_links(soup)

        if not hits:
            self.log("No candidate links found on search page.")
            return []

        # Keep strong if any exist, else keep any scored hits
        scores = [s for s, _ in hits]
        if any(s >= 2 for s in scores):
            urls = [u for s, u in hits if s >= 2]
        else:
            urls = [u for s, u in hits]

        urls = urls[: self.max_results]
        self.log(f"Selected {len(urls)} result link(s).")
        return urls

    # -------------------------
    # Detail page scraping
    # -------------------------
    def _scrape_detail_page(self, url: str) -> Dict[str, str]:
        html = self._get(url)
        data: Dict[str, str] = {"Detail Page URL": url}

        if not html:
            data["Title"] = ""
            data["Error"] = "Failed to fetch detail page"
            return data

        soup = BeautifulSoup(html, "html.parser")

        # Title
        title = ""
        og = soup.select_one('meta[property="og:title"]')
        if og and og.get("content"):
            title = og["content"].strip()
        if not title:
            h1 = soup.select_one("h1")
            if h1:
                title = h1.get_text(" ", strip=True)
        data["Title"] = title

        # Description
        desc = ""
        ogd = soup.select_one('meta[property="og:description"]')
        if ogd and ogd.get("content"):
            desc = ogd["content"].strip()
        data["Description"] = desc

        # Common pattern: <dl><dt>Label</dt><dd>Value</dd></dl>
        for dl in soup.select("dl"):
            for dt in dl.select("dt"):
                label = dt.get_text(" ", strip=True).strip().rstrip(":")
                dd = dt.find_next_sibling("dd")
                value = dd.get_text(" ", strip=True).strip() if dd else ""
                if label and value and label not in data:
                    data[label] = value

        return data

    # -------------------------
    # Main / Excel
    # -------------------------
    def scrape(self) -> pd.DataFrame:
        if not self.title:
            return pd.DataFrame(columns=["Title", "Detail Page URL", "Description"])

        search_url, html = self.perform_search()
        if not html:
            return pd.DataFrame([{ 
                "Title": "",
                "Detail Page URL": search_url,
                "Description": "",
                "Error": "Failed to fetch search page"
            }])

        # If search page looks like a detail/work page, scrape it directly.
        soup = BeautifulSoup(html, "html.parser")
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get("content") and "/view/" in (self.session.head(search_url, allow_redirects=True).url or ""):
            self.log("Search appears to have redirected to a view/work page.")
            detail = self._scrape_detail_page(search_url)
            return pd.DataFrame([detail])

        urls = self.extract_list_page_links(html)
        if not urls:
            return pd.DataFrame(columns=["Title", "Detail Page URL", "Description"])

        films: List[Dict[str, str]] = []
        for u in urls:
            films.append(self._scrape_detail_page(u))

        df = pd.DataFrame(films)
        if df.empty:
            return pd.DataFrame(columns=["Title", "Detail Page URL", "Description"])

        # Title-score filtering (no exact match)
        if "Title" in df.columns:
            scores = df["Title"].fillna("").apply(self._title_score)
            if (scores >= 2).any():
                df = df.loc[scores >= 2].copy()
            elif (scores > 0).any():
                df = df.loc[scores > 0].copy()

        df = df.drop_duplicates().reset_index(drop=True)
        return df

    def process(self) -> Tuple[io.BytesIO, str]:
        df = self.scrape()

        buffer = io.BytesIO()
        safe = re.sub(r"\s+", "_", self.title.strip()) if self.title else "alexander"
        filename = f"alexander_street_search_results_{safe}.xlsx"

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Alexander Street Press Results")

        buffer.seek(0)
        return buffer, filename
