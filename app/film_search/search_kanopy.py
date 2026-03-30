APP_ROOT = Path(__file__).resolve().parent
SELENIUM_CACHE = APP_ROOT / ".selenium"
LATEST_META_URL = (
    "https://googlechromelabs.github.io/"
    "chrome-for-testing/last-known-good-versions-with-downloads.json"
)


@contextmanager
def file_lock(lock_path: Path):
    """
    Simple inter-process lock for multi-worker Flask/Gunicorn on Linux.
    """
    import fcntl

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def _extract_zip(zip_path: Path, extract_to: Path) -> None:
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)


def _find_file(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not find {name} under {root}")
    return matches[0]


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ensure_latest_chrome_runtime() -> Tuple[str, str]:
    """
    Downloads the latest stable Chrome for Testing browser + chromedriver
    into APP_ROOT/.selenium and returns:
        (chrome_binary_path, chromedriver_path)
    """
    SELENIUM_CACHE.mkdir(parents=True, exist_ok=True)

    lock_file = SELENIUM_CACHE / ".download.lock"
    with file_lock(lock_file):
        with urllib.request.urlopen(LATEST_META_URL, timeout=60) as resp:
            meta = json.load(resp)

        stable = meta["channels"]["Stable"]
        version = stable["version"]

        chrome_url = None
        driver_url = None

        for item in stable["downloads"]["chrome"]:
            if item["platform"] == "linux64":
                chrome_url = item["url"]
                break

        for item in stable["downloads"]["chromedriver"]:
            if item["platform"] == "linux64":
                driver_url = item["url"]
                break

        if not chrome_url or not driver_url:
            raise RuntimeError("Could not find linux64 Chrome/ChromeDriver download URLs")

        version_root = SELENIUM_CACHE / version
        browser_root = version_root / "chrome"
        driver_root = version_root / "driver"

        chrome_binary = browser_root / "chrome-linux64" / "chrome"
        chromedriver_binary = driver_root / "chromedriver-linux64" / "chromedriver"

        if chrome_binary.exists() and chromedriver_binary.exists():
            _make_executable(chrome_binary)
            _make_executable(chromedriver_binary)
            return str(chrome_binary), str(chromedriver_binary)

        with tempfile.TemporaryDirectory(dir=SELENIUM_CACHE) as tmpdir:
            tmpdir = Path(tmpdir)
            chrome_zip = tmpdir / "chrome.zip"
            driver_zip = tmpdir / "chromedriver.zip"

            _download(chrome_url, chrome_zip)
            _download(driver_url, driver_zip)

            _extract_zip(chrome_zip, browser_root)
            _extract_zip(driver_zip, driver_root)

        chrome_binary = _find_file(browser_root, "chrome")
        chromedriver_binary = _find_file(driver_root, "chromedriver")

        _make_executable(chrome_binary)
        _make_executable(chromedriver_binary)

        current_root = SELENIUM_CACHE / "current"
        if current_root.exists() or current_root.is_symlink():
            if current_root.is_symlink() or current_root.is_file():
                current_root.unlink()
            else:
                shutil.rmtree(current_root)
        current_root.symlink_to(version_root, target_is_directory=True)

        return str(chrome_binary), str(chromedriver_binary)

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


class SearchKanopy(_TitleScorerMixin):
    """
    Selenium scraper for Kanopy search.
    Loads https://www.kanopy.com/en/tufts/search
    Enters a search term and visits matching results.

    Updated:
      - Uses title scoring instead of exact title equality.
      - Filters to strong matches (score>=2) if any exist; otherwise keeps score>0; otherwise keeps all.
    """

    SEARCH_URL = "https://www.kanopy.com/en/tufts/search"

    def __init__(self, film_title: str, debug: bool = True, max_results: int = 25):
        self.film_title = (film_title or "").strip()
        self.debug = debug
        self.max_results = max_results

    def log(self, msg: str):
        if self.debug:
            print(f"[KANOPY] {msg}", flush=True)

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
        driver = webdriver.Chrome(executable_path=driver_path, chrome_options=chrome_options)
        driver.set_page_load_timeout(60)
        return driver

    # -------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------
    def load_search_results(self, driver, wait):
        driver.get(self.SEARCH_URL)

        search_input = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Search"]'))
        )
        search_input.clear()
        search_input.send_keys(self.film_title)
        search_input.send_keys(Keys.ENTER)
        time.sleep(3)

    def collect_result_links(self, driver, wait) -> List[str]:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.title")))

        title_nodes = driver.find_elements(By.CSS_SELECTOR, "div.title")
        hits: List[Tuple[int, str]] = []

        for node in title_nodes:
            title_text = (node.text or "").strip()
            if not title_text:
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

            if not href:
                continue

            score = self._title_score(title_text, want=self.film_title)
            if score > 0:
                hits.append((score, href))

        # Prefer strong matches if any exist
        if any(s >= 2 for s, _ in hits):
            hits = [(s, u) for s, u in hits if s >= 2]

        hits.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate, cap
        deduped: List[str] = []
        seen = set()
        for _, link in hits:
            abs_link = urljoin("https://www.kanopy.com", link)
            if abs_link in seen:
                continue
            seen.add(abs_link)
            deduped.append(abs_link)
            if len(deduped) >= self.max_results:
                break

        self.log(f"Selected {len(deduped)} matching result link(s) after title scoring.")
        return deduped

    # -------------------------------------------------------------
    # DETAIL PAGE
    # -------------------------------------------------------------
    def scrape_detail_page(self, driver, wait) -> Dict[str, str]:
        data: Dict[str, str] = {"Detail Page URL": driver.current_url}

        try:
            h3 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h3")))
            data["Film Title"] = (h3.text or "").strip()
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

        # Section header + sibling items
        info_sections = driver.find_elements(By.CSS_SELECTOR, "h2.info-section-title")
        for h2 in info_sections:
            label = (h2.text or "").strip()
            if not label:
                continue

            values: List[str] = []
            try:
                section_container = h2.find_element(
                    By.XPATH, "./ancestor::div[contains(@class,'info-section-container')][1]"
                )
                links = section_container.find_elements(
                    By.CSS_SELECTOR,
                    "div.term-info-section-items div.term-info-section-item a"
                )
                values = [a.text.strip() for a in links if a.text and a.text.strip()]
            except Exception:
                values = []

            data[label] = "; ".join(values) if values else ""

        return data

    # -------------------------------------------------------------
    # DataFrame + filtering
    # -------------------------------------------------------------
    def build_dataframe(self, films: List[Dict[str, str]]) -> pd.DataFrame:
        if not films:
            return pd.DataFrame(columns=["Detail Page URL", "Film Title"])

        # Column order based on first appearance
        ordered_columns: List[str] = []
        for film in films:
            for key in film.keys():
                if key not in ordered_columns:
                    ordered_columns.append(key)

        rows = []
        for film in films:
            row = {col: "" for col in ordered_columns}
            row.update({k: (v if v is not None else "") for k, v in film.items()})
            rows.append(row)

        df = pd.DataFrame(rows, columns=ordered_columns)
        if df.empty:
            return df

        # Title-score filter
        if "Film Title" in df.columns:
            scores = df["Film Title"].fillna("").apply(lambda t: self._title_score(t, want=self.film_title))
            if (scores >= 2).any():
                df = df.loc[scores >= 2].copy()
            elif (scores > 0).any():
                df = df.loc[scores > 0].copy()

        return df.drop_duplicates(keep="first").reset_index(drop=True)

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

            films: List[Dict[str, str]] = []
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
