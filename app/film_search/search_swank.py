import io
import re
import time
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SwankSearch:

    def __init__(self, film_title):
        self.film_title = film_title

    # ----------------------------------------------------------
    # GDPR close helper
    # ----------------------------------------------------------
    def close_gdpr(self, driver):
        try:
            time.sleep(2)
            aside = driver.find_element(By.CSS_SELECTOR, "aside#usercentrics-cmp-ui")
            root = driver.execute_script("return arguments[0].shadowRoot", aside)
            accept = driver.execute_script(
                "return arguments[0].querySelector('button.uc-accept-button#accept');",
                root
            )
            accept.click()
            time.sleep(1)
        except:
            pass

    # ----------------------------------------------------------
    # Scraper
    # ----------------------------------------------------------
    def scrape_films(self, driver, wait):
        films = []

        container = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.carousel-holder.carousel-holder-posters")
            )
        )

        # raw matches
        raw_links = container.find_elements(
            By.XPATH,
            ".//div[contains(@class,'panel-carousel-image-holder')]//a[contains(@href,'/details/')]"
        )

        # filter visible
        film_links = [
            l for l in raw_links
            if l.is_displayed() and l.size["height"] > 10 and l.size["width"] > 10
        ]

        for i in range(len(film_links)):

            # re-fetch after navigation
            container = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.carousel-holder.carousel-holder-posters")
                )
            )
            raw_links = container.find_elements(
                By.XPATH,
                ".//div[contains(@class,'panel-carousel-image-holder')]//a[contains(@href,'/details/')]"
            )
            film_links = [
                l for l in raw_links
                if l.is_displayed() and l.size["height"] > 10 and l.size["width"] > 10
            ]

            if i >= len(film_links):
                break

            link = film_links[i]
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
            time.sleep(0.5)

            try:
                link.click()
            except:
                continue

            # detail page
            film_info = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.film-info"))
            )

            film_record = {}
            film_record["Detail Page URL"] = driver.current_url

            try:
                title_text = film_info.find_element(By.TAG_NAME, "h1").text.strip()
            except:
                title_text = ""
            film_record["Film Title"] = title_text

            blocks = film_info.find_elements(By.CSS_SELECTOR, "div")

            for b in blocks:
                try:
                    h2 = b.find_element(By.TAG_NAME, "h2").text.strip()
                    p = b.find_element(By.TAG_NAME, "p").text.strip()
                    film_record[h2] = p
                except:
                    continue

            films.append(film_record)

            driver.back()
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.carousel-holder.carousel-holder-posters")
                )
            )
            time.sleep(1)

        return films

    # ----------------------------------------------------------
    # Main method used by Flask route
    # ----------------------------------------------------------
    def process(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=Service(), options=options)
        wait = WebDriverWait(driver, 25)

        try:
            driver.get("https://www.swank.com/")
            time.sleep(3)
            self.close_gdpr(driver)

            driver.set_window_size(400, 1000)
            time.sleep(1)
            driver.execute_script("window.scrollTo(0,0);")

            # open search
            search_icon = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.nav-search-mobile.visible-xs")
                )
            )
            search_icon.click()
            time.sleep(1)

            # license dropdown
            dropdown = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(normalize-space(.), 'Please select')]")
                )
            )
            dropdown.click()
            time.sleep(1)

            campus = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(text(),'Campus License')]")
                )
            )
            campus.click()
            time.sleep(1)

            # search bar
            search_box = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "input[placeholder='Start typing to search']")
                )
            )

            search_box.clear()
            search_box.send_keys(self.film_title)
            search_box.send_keys(Keys.RETURN)

            time.sleep(3)

            films = self.scrape_films(driver, wait)

        finally:
            driver.quit()

        # build DataFrame
        df = pd.DataFrame(films)
        output = io.BytesIO()

        safe_title = re.sub(r'[\\/*?:"<>|]', "_", self.film_title)
        filename = f"Swank {safe_title} results.xlsx"

        df.to_excel(output, index=False)
        output.seek(0)

        return output, filename
