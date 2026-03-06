# search_criterion.py
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


class SearchCriterion(_TitleScorerMixin):
    """
    Criterion scraper using ONLY requests + BeautifulSoup.

    - Searches the Criterion "media3.criterionpic.com" endpoint
    - Parses search results into detail-page links
    - Scrapes detail pages with malformed HTML safely (label/value td pairing)
    - Uses title scoring (strong match preferred) instead of exact title equality
    """

    BASE = "https://media3.criterionpic.com"
    BASE_SEARCH = (
        "https://media3.criterionpic.com/htbin/wwform/014/wwt770"
        "?kw={kw}&task=search&ad=AndPlusOr&option=com_search&Itemid=101"
    )

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, film_title: str, debug: bool = False, max_results: int = 25):
        self.title = (film_title or "").strip()
        self.debug = debug
        self.max_results = max_results
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def log(self, msg: str) -> None:
        if self.debug:
            print(f"[CRITERION] {msg}", flush=True)

    def _get(self, url: str, timeout: int = 25) -> Optional[str]:
        self.log(f"GET {url}")
        try:
            r = self.session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as e:
            self.log(f"GET failed: {e}")
            return None

    def _abs_url(self, href: str) -> str:
        return urljoin(self.BASE, href or "")

    @staticmethod
    def _clean_text(s: str) -> str:
        s = (s or "").replace("\xa0", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # -----------------------
    # Search
    # -----------------------
    def perform_search(self) -> Tuple[str, Optional[str]]:
        kw = quote_plus(self.title)
        url = self.BASE_SEARCH.format(kw=kw)
        html = self._get(url)
        return url, html

    def _is_detail_page_html(self, html: str) -> bool:
        if not html:
            return False
        return ("dy_cat_long_ftitle" in html) and ("dy_cat_label_col" in html)

    def extract_list_page_links(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: List[Tuple[int, str]] = []

        for span in soup.select("span.dy_cat_poster_title"):
            a = span.find_parent("a") or span.find("a")
            if not a:
                continue
            href = a.get("href") or ""
            if not href:
                continue
            text = self._clean_text(a.get_text(" ", strip=True))
            score = self._title_score(text)
            if score > 0:
                urls.append((score, self._abs_url(href)))

        urls.sort(key=lambda x: x[0], reverse=True)

        seen = set()
        out: List[str] = []
        for _, u in urls:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
            if len(out) >= self.max_results:
                break

        self.log(f"List page links selected: {len(out)}")
        return out

    # -----------------------
    # Detail page
    # -----------------------
    def _extract_title(self, soup: BeautifulSoup) -> str:
        title_span = soup.select_one("span.dy_cat_long_ftitle")
        if title_span:
            return self._clean_text(title_span.get_text(" ", strip=True))
        t = soup.select_one("title")
        return self._clean_text(t.get_text(" ", strip=True)) if t else ""

    def _label_direct_text(self, td) -> str:
        direct = [self._clean_text(s) for s in td.find_all(string=True, recursive=False)]
        direct = [d for d in direct if d]
        if direct:
            return self._clean_text(" ".join(direct))
        return self._clean_text(td.get_text(" ", strip=True))

    def scrape_detail_page(self, url: str) -> Dict[str, str]:
        html = self._get(url)
        data: Dict[str, str] = {"Detail Page URL": url}

        if not html:
            data["Title"] = ""
            data["Error"] = "Failed to fetch detail page"
            return data

        soup = BeautifulSoup(html, "html.parser")
        data["Title"] = self._extract_title(soup)

        nodes = soup.select("td.dy_cat_label_col, td.dy_cat_full_desc_col")

        current_label: Optional[str] = None
        for node in nodes:
            cls = node.get("class") or []
            if "dy_cat_label_col" in cls:
                label = self._label_direct_text(node).rstrip(":").strip()
                if not label or len(label) > 60:
                    current_label = None
                    continue
                current_label = label
            elif "dy_cat_full_desc_col" in cls and current_label:
                value = self._clean_text(node.get_text(" ", strip=True))
                data[current_label] = value
                current_label = None

        return data

    # -----------------------
    # Main / Excel
    # -----------------------
    def scrape(self) -> pd.DataFrame:
        if not self.title:
            return pd.DataFrame(columns=["Detail Page URL", "Title"])

        search_url, html = self.perform_search()
        if not html:
            return pd.DataFrame([{ "Detail Page URL": search_url, "Title": "", "Error": "Failed to fetch search page" }])

        if self._is_detail_page_html(html):
            self.log("Search response looks like a detail page; scraping directly.")
            return pd.DataFrame([self.scrape_detail_page(search_url)])

        links = self.extract_list_page_links(html)
        if not links:
            return pd.DataFrame(columns=["Detail Page URL", "Title"])

        films = [self.scrape_detail_page(href) for href in links]
        df = pd.DataFrame(films)

        if not df.empty and "Title" in df.columns:
            scores = df["Title"].fillna("").apply(self._title_score)
            if (scores >= 2).any():
                df = df.loc[scores >= 2].copy()
            elif (scores > 0).any():
                df = df.loc[scores > 0].copy()

        return df.drop_duplicates().reset_index(drop=True)

    def process(self) -> Tuple[io.BytesIO, str]:
        df = self.scrape()
        buffer = io.BytesIO()
        filename = f"criterion_search_results_{self.title.replace(' ', '_')}.xlsx"

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Criterion Results")

        buffer.seek(0)
        return buffer, filename
