#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup


class _TitleScorerMixin:
    @staticmethod
    def _norm_spaces(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "")).strip()

    @staticmethod
    def _norm_compact(s: str) -> str:
        # ignore punctuation/spaces for matching
        return re.sub(r"\W+", "", (s or "").lower())

    def _title_score(self, candidate: str, want: Optional[str] = None) -> int:
        """
        3 = exact compact match (ignore punctuation)
        2 = exact normalized match (spaces collapsed, case-insensitive)
        1 = contains
        0 = no match
        """
        want = (want if want is not None else getattr(self, "title", "")) or ""
        want = want.strip()
        candidate = (candidate or "").strip()

        want_comp = self._norm_compact(want)
        cand_comp = self._norm_compact(candidate)

        if want_comp and cand_comp == want_comp:
            return 3

        want_norm = self._norm_spaces(want).lower()
        cand_norm = self._norm_spaces(candidate).lower()

        if want_norm and cand_norm == want_norm:
            return 2

        if want_norm and want_norm in cand_norm:
            return 1

        return 0


class DocuseekScraper(_TitleScorerMixin):
    """
    Docuseek2 scraper (requests + BeautifulSoup)

    Flow:
      1) POST keyword search to /cart/advsearch/hf
      2) Extract detail-page links from results HTML
      3) GET each detail page with the SAME session (cookies)
      4) Parse sidebar metadata (<div class="sidebar"> ... <p><strong>Label:</strong> Value</p>)
      5) Return Excel buffer + filename for Flask send_file()

    Fixes:
      - Robust title extraction (avoids accessibility heading 'Main content')
      - Robust label/value extraction (doesn't rely on strong.next_sibling whitespace)
      - Title-score filtering (>=2 preferred, else >0, else keep all)
    """

    SEARCH_ENDPOINT = "https://docuseek2.com/cart/advsearch/hf"

    def __init__(self, film_title: str, debug: bool = False, max_results: int = 25):
        self.title = (film_title or "").strip()
        self.debug = debug
        self.max_results = max_results

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def log(self, msg: str) -> None:
        if self.debug:
            print(f"[DOCUSEEK] {msg}", flush=True)

    # -------------------------
    # HTTP helpers
    # -------------------------
    def _get_html(self, url: str, timeout: int = 45) -> str:
        self.log(f"GET {url}")
        r = self.session.get(url, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r.text

    def _post_html(self, url: str, data: Dict[str, str], timeout: int = 45) -> str:
        self.log(f"POST {url} data={list(data.keys())}")
        r = self.session.post(url, data=data, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r.text

    @staticmethod
    def _soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html or "", "html.parser")

    @staticmethod
    def _clean_text(s: str) -> str:
        s = (s or "").replace("\xa0", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # -------------------------
    # Search
    # -------------------------
    def _search_html(self) -> str:
        # Establish cookies
        _ = self._get_html(self.SEARCH_ENDPOINT)
        # Run search
        return self._post_html(self.SEARCH_ENDPOINT, {"ckeywords": self.title})

    def _extract_detail_urls(self, soup: BeautifulSoup) -> List[str]:
        urls: List[str] = []

        for a in soup.select("#searchresults .result h3.title a[href]"):
            urls.append(a["href"])

        if not urls:
            for a in soup.select(".result h3.title a[href]"):
                urls.append(a["href"])

        urls = list(dict.fromkeys(urls))
        urls = urls[: self.max_results]
        self.log(f"Found {len(urls)} result link(s).")
        return urls

    # -------------------------
    # Detail parsing
    # -------------------------
    def _extract_title(self, soup: BeautifulSoup) -> str:
        def good(t: str) -> bool:
            t = self._clean_text(t)
            if not t:
                return False
            return t.lower().strip() not in {"main content", "content", "main"}

        # Best: og:title
        og = soup.select_one('meta[property="og:title"]')
        if og and og.get("content"):
            t = self._clean_text(og["content"])
            if good(t):
                return t

        # Then: likely headings (note: avoid taking generic h1 if it's "Main content")
        for sel in (
            "h1.title",
            "h1.page-title",
            "h1.entry-title",
            "h1.product-title",
            "h1",
            "h3.title",
            "h2.title",
        ):
            el = soup.select_one(sel)
            if el:
                t = self._clean_text(el.get_text(" ", strip=True))
                if good(t):
                    return t

        # Fallback: <title>
        tt = soup.select_one("title")
        if tt:
            t = self._clean_text(tt.get_text(" ", strip=True))
            t = re.sub(r"\s*\|\s*Docuseek.*$", "", t, flags=re.I).strip()
            if good(t):
                return t

        return ""

    def _parse_sidebar(self, soup: BeautifulSoup) -> Dict[str, str]:
        out: Dict[str, str] = {}
        ps = soup.select("div.sidebar p")
        if not ps:
            return out

        for p in ps:
            strong = p.find("strong")
            if not strong:
                continue

            label = self._clean_text(strong.get_text(" ", strip=True)).rstrip(":").strip()
            if not label:
                continue

            # Collect all text AFTER <strong> within the <p>
            parts: List[str] = []
            for sib in strong.next_siblings:
                if isinstance(sib, str):
                    txt = self._clean_text(sib)
                else:
                    txt = self._clean_text(sib.get_text(" ", strip=True))
                if txt:
                    parts.append(txt)

            value = self._clean_text(" ".join(parts))
            if value:
                out[label] = value

        return out

    def _scrape_detail(self, url: str) -> Dict[str, str]:
        html = self._get_html(url)
        soup = self._soup(html)

        data: Dict[str, str] = {"Detail Page URL": url}
        data["Title"] = self._extract_title(soup)
        data.update(self._parse_sidebar(soup))
        return data

    # -------------------------
    # Main
    # -------------------------
    def scrape(self) -> pd.DataFrame:
        if not self.title:
            return pd.DataFrame(columns=["Detail Page URL", "Title"])

        html = self._search_html()
        soup = self._soup(html)

        urls = self._extract_detail_urls(soup)
        if not urls:
            return pd.DataFrame(columns=["Detail Page URL", "Title"])

        rows: List[Dict[str, str]] = []
        for u in urls:
            try:
                rows.append(self._scrape_detail(u))
            except Exception as e:
                self.log(f"Detail scrape failed for {u}: {e}")
                rows.append({"Detail Page URL": u, "Title": "", "Error": str(e)})

        df = pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)
        if df.empty:
            return df

        # Requested title-score filtering structure (using Title)
        if not df.empty and "Title" in df.columns:
            scores = df["Title"].fillna("").apply(lambda t: self._title_score(t, want=self.title))
            if (scores >= 2).any():
                df = df.loc[scores >= 2].copy()
            elif (scores > 0).any():
                df = df.loc[scores > 0].copy()

        # Soft drop: only remove rows with truly empty titles after filtering
        if "Title" in df.columns:
            df = df[df["Title"].fillna("").astype(str).str.strip() != ""].reset_index(drop=True)

        return df

    def process(self) -> Tuple[io.BytesIO, str]:
        df = self.scrape()

        buffer = io.BytesIO()
        safe = re.sub(r"[^A-Za-z0-9]+", "_", self.title).strip("_") or "docuseek"
        filename = f"docuseek_results_{safe}.xlsx"

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Docuseek Results")

        buffer.seek(0)
        return buffer, filename
