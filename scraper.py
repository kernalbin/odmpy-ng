from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time

class Scraper:
    """Overdrive Audiobook Scraper"""
    def __init__(self, config, headless=True):
        self.config = config

        # Fix URL construction - use the full library URL provided in config
        self.base_url = config["library"]
        if not self.base_url.startswith("https://"):
            self.base_url = "https://" + self.base_url

        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("--log-level=2")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--start-maximized")
        self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        self.driver = None

    def __del__(self):
        self.driver.quit()

    def getCookies(self):
        return self.driver.get_cookies().copy()

    def _login(self) -> list[dict]:
        # Need to sign in again
        print("Logging in...")
        self.driver.get(self.base_url + "/account/ozone/sign-in")

        try:
            cookies_dialog = self.driver.find_element(By.CLASS_NAME, 'cookie-banner-close-button')
            cookies_dialog.click()
        except:
            pass

        signin_button = self.driver.find_element(By.CLASS_NAME, 'signin-button')
        username_input = self.driver.find_element(By.ID, 'username')
        password_input = self.driver.find_element(By.ID, 'password')

        wait = WebDriverWait(self.driver, timeout=15)
        wait.until(lambda _ : signin_button.is_enabled())

        username_input.send_keys(self.config['user'])
        password_input.send_keys(self.config['pass'])

        signin_button.click()

        time.sleep(1)

        if 'sign-in' in self.driver.current_url.lower():
            return []

        return self.driver.get_cookies()

    def ensureLogin(self, cookies: list[dict]) -> list[dict]: # Can pass in []

        # Create webdriver session and add given cookies if they exist.
        if not self.driver:
            # Use webdriver-manager to handle Chrome driver installation and initialization
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
            self.driver.get(self.base_url)
            try:
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
            except:
                print("Invalid cookies")
                return self._login()

        # Go to authenticated page to test if cookies are still valid
        self.driver.get(self.base_url + "/account/loans")

        try:
            loans_title = self.driver.find_element(By.CLASS_NAME, 'account-title')
            if loans_title:
                if "Loans" in loans_title.text:
                    # Already have valid session
                    return cookies
            return self._login()
        except NoSuchElementException:
            
            # Get new valid session
            return self._login()

    def getLoans(self):

        print("Finding books...")
        self.driver.get(self.base_url + "/account/loans")

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'Loans-TitleContainerRight'))
            )
        except Exception as e:
            print(f"Failed to get loans, not loading correctly: {e}")
            return []

        books = []
        loan_blocks = self.driver.find_elements(By.CLASS_NAME, 'Loans-TitleContainerRight')

        for index,block in enumerate(loan_blocks):
            try:
                title_element = block.find_element(By.CLASS_NAME, 'title-name')
                author_element = block.find_element(By.CLASS_NAME, 'secondary-underline')
                listen_link = block.find_element(By.PARTIAL_LINK_TEXT, 'Listen now').get_attribute('href')

                book_id = listen_link.split('/')[-1]

                books.append({"index": index, "title": title_element.text.strip(), "author": author_element.text.strip(), "link": listen_link, "id": book_id})
            except Exception as e:
                print(f"Failed to parse loan at index {index}: {e}")

        return books

    def getBook(self, selected_title_link):

        self.driver.get(selected_title_link)

        time.sleep(1)

        chapter_previous = self.driver.find_element(By.CLASS_NAME, 'chapter-bar-prev-button')
        chapter_next = self.driver.find_element(By.CLASS_NAME, 'chapter-bar-next-button')

        time_previous = self.driver.find_element(By.CLASS_NAME, 'playback-controls-left')
        time_next = self.driver.find_element(By.CLASS_NAME, 'playback-controls-right')

        timeline_percent = self.driver.find_element(By.CLASS_NAME, 'timeline-percent-visual')

        timeline_length = self.driver.find_element(By.CLASS_NAME, 'timeline-end-minutes').find_element(By.CLASS_NAME, 'place-phrase-visual')
        timeline_current_time = self.driver.find_element(By.CLASS_NAME, 'timeline-start-minutes').find_element(By.CLASS_NAME, 'place-phrase-visual')

        chapter_title = self.driver.find_element(By.CLASS_NAME, 'chapter-bar-title')

        time.sleep(1)

        while chapter_previous.is_enabled():
            chapter_previous.click()
            time.sleep(.2)
        time.sleep(1)

        expected_time = timeline_length.get_attribute("textContent").replace("-", "")
        print(f"End file should be ~{expected_time} in length.")

        chapter_markers = {}

        chapter_markers[chapter_title.get_attribute("textContent")] = timeline_current_time.get_attribute("textContent")

        while chapter_next.is_enabled():
            print(timeline_percent.text)
            chapter_next.click()
            time.sleep(2)
            if not chapter_title.get_attribute("textContent") in chapter_markers:
                chapter_markers[chapter_title.get_attribute("textContent")] = timeline_current_time.get_attribute("textContent")
            for i in range(2):
                time_previous.click()
                time.sleep(.15)
            for i in range(4):
                time_next.click()
                time.sleep(.15)
            time.sleep(.3)

        urls = {}

        for request in self.driver.requests:
            if request.response:
                if '.mp3' in request.url:
                    part_id = request.url.split("Part")[1].split(".mp3")[0]
                    if part_id not in urls:
                        urls[part_id] = request.url
                if '.jpg' in request.url:
                    if 'listen.overdrive.com' in request.url:
                        cover_image_url = request.url

        return (urls, chapter_markers, cover_image_url, expected_time)