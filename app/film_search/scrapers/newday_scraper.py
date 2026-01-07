import io
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict


class NewDayScraper:
    """
    Scrapes New Day Films by TITLE.
    Steps:
      1. Build search URL from user title
      2. Parse list of matching films
      3. Scrape each film's detail page
      4. Return Excel buffer + filename
    """

    SEARCH_ENDPOINT = "https://www.newday.com/search?text={}"

    def __init__(self, title: str, debug: bool = False):
        self.title = title.strip()
        self.debug = debug

    def log(self, msg: str):
        if self.debug:
            print(f"[NEWDAY] {msg}", flush=True)

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
            timeout=20,
        )
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    # ---------------------------------------------------------
    # Build Search URL
    # ---------------------------------------------------------
    def _build_search_url(self) -> str:
        from urllib.parse import quote_plus
        return self.SEARCH_ENDPOINT.format(quote_plus(self.title))

    # ---------------------------------------------------------
    # Extract film detail URLs from search results
    # ---------------------------------------------------------
    def _extract_detail_urls(self, soup: BeautifulSoup) -> List[str]:
        urls = []
        for a in soup.select("a[href^='/films/']"):
            link = "https://www.newday.com" + a["href"]
            urls.append(link)

        urls = list(dict.fromkeys(urls))  # unique in order
        self.log(f"Found {len(urls)} film hits.")
        return urls

    # ---------------------------------------------------------
    # Scrape individual film detail page
    # ---------------------------------------------------------
    def _scrape_detail(self, url: str) -> Dict[str, str]:
        soup = self._fetch_soup(url)
        data = {"Detail Page URL": url}

        # ------------------------
        # Title
        # ------------------------
        title_el = soup.select_one("#page-title span")
        data["Title"] = title_el.get_text(strip=True) if title_el else ""

        # ------------------------
        # Logline / Description
        # ------------------------
        logline = soup.select_one(".field--field-logline .field__item")
        data["Logline"] = logline.get_text(" ", strip=True) if logline else ""

        # ------------------------
        # Filmmaker(s)
        # ------------------------
        filmmakers = soup.select(".header-details__filmmakers .field__item a")
        data["Filmmaker"] = ", ".join(a.get_text(strip=True) for a in filmmakers) if filmmakers else ""

        # ------------------------
        # Release Year
        # ------------------------
        year_el = soup.select_one(".field--field-release-year .field__item")
        data["Year Released"] = year_el.get_text(strip=True) if year_el else ""

        # ------------------------
        # Runtime
        # ------------------------
        runtime_el = soup.select_one(".field--field-film-length .field__item")
        data["Runtime"] = runtime_el.get_text(strip=True) if runtime_el else ""

        # ------------------------
        # Closed Captioning
        # ------------------------
        cc_el = soup.select_one(".header-details__features [title='Closed Captioning']")
        data["Closed Captioning"] = "Yes" if cc_el else "No"

        # ------------------------
        # Trailer (optional)
        # ------------------------
        trailer = soup.select_one("lite-youtube")
        if trailer and trailer.get("videoid"):
            data["Trailer VideoID"] = trailer["videoid"]
        else:
            data["Trailer VideoID"] = ""

        return data


    # ---------------------------------------------------------
    # Build DataFrame
    # ---------------------------------------------------------
    def scrape(self) -> pd.DataFrame:
        search_url = self._build_search_url()
        soup = self._fetch_soup(search_url)

        detail_urls = self._extract_detail_urls(soup)

        films = []
        for url in detail_urls:
            films.append(self._scrape_detail(url))

        df = pd.DataFrame(films)
        if not df.empty:
            df = df.drop_duplicates().reset_index(drop=True)


        df = df[~(df["Title"].isna())&(df["Title"]!="")]
        df = df.reset_index(drop=True)

        return df

    # ---------------------------------------------------------
    # Excel output
    # ---------------------------------------------------------
    def process(self):
        df = self.scrape()

        buffer = io.BytesIO()
        safe = re.sub(r"[^A-Za-z0-9]", "_", self.title) or "newday"
        filename = f"newday_results_{safe}.xlsx"

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="NewDay Results")

        buffer.seek(0)
        return buffer, filename
