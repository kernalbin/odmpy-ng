from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import overdrive_download
import convert_metadata
import os
import time
import sys

class Scraper:
    """Automated Overdrive audiobook downloader using Selenium."""
    def __init__(self, config, headless=True):
        """
        Initializes the scraper with user configuration and sets up the Chrome driver.

        Args:
            config (dict): Dictionary with keys 'library', 'user', 'pass', etc.
            headless (bool): Whether to run the browser in headless mode.
        """
        self.config = config
        self.chapter_seconds = []

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
        self.chrome_options.add_argument("--mute-audio")

        self.driver = None

    def __del__(self):
        if self.driver:
            self.driver.quit()

    def get_cookies(self):
        """Returns the current browser session cookies."""
        return self.driver.get_cookies().copy()

    def _login(self) -> list[dict]:
        """Handles login logic and returns a fresh list of cookies."""
        print("Logging in...")
        self.driver.get(self.base_url + "/account/ozone/sign-in")

        # Dismiss cookie banner if present
        try:
            self.driver.find_element(By.CLASS_NAME, 'cookie-banner-close-button').click()
        except:
            pass

        # Enter credentials
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

        return self.get_cookies()

    def ensure_login(self, cookies: list[dict]) -> list[dict]: # Can pass in []
        """
        Ensures the user is logged in; attempts to use existing cookies.

        Args:
            cookies (list[dict]): Optional pre-existing cookies.

        Returns:
            list[dict]: Valid session cookies.
        """
        if not self.driver:
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

    def get_loans(self):
        """
        Retrieves all current audiobook loans for the user.

        Returns:
            list: List of dictionaries with book info: title, author, link, and ID.
        """
        print("Finding books...")
        self.driver.get(self.base_url + "/account/loans")

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'Loans-TitleContainerRight'))
            )
        except Exception as e:
            print(f"Failed to load loans: {e}")
            sys.exit(4)

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
    
    def has_url(self, part_num) -> bool:
        mp3_urls = self.requests_to_mp3_files()
        url = mp3_urls.get(f"{part_num:02d}")
        return url is not None

    def requests_to_mp3_files(self) -> dict:
        """
        Extracts MP3 file URLs from the browser's request history.

        Returns:
            dict: Part ID to URL mapping.
        """
        urls = {}

        for request in self.driver.requests:
            if request.response:
                if '.mp3' in request.url:
                    part_id = request.url.split("Part")[1].split(".mp3")[0]
                    if part_id not in urls:
                        urls[part_id] = request.url
        return urls

    def chapter_containing(self, current_location) -> int:
        # Don't enumerate the last element, it's actually the end of the book.
        for i, start in enumerate(self.chapter_seconds[:-1]):
            if current_location >= start and current_location < self.chapter_seconds[i+1]:
                return i
        # Account for the end of the book.
        return len(self.chapter_seconds) - 2
    
    def extract_minutes_to_seconds(self, raw_text: str):
        """
        Parses a string like '2m' to integer seconds.

        Args:
            raw_text (str): Text to parse.

        Returns:
            int or bool: Parsed seconds, or False on failure.
        """
        if not raw_text:
            return False
        cleaned = raw_text.strip().lower()  # remove whitespace and lowercase
        if cleaned.endswith("m"):
            minutes = int(cleaned[:-1].replace(',', ''))  # remove the 'm' and convert to seconds
            return minutes * 60
        return False

    def get_book(self, selected_title_link: str, download_path: str):
        """
        Downloads the selected audiobook and associated metadata.

        Args:
            selected_title_link (str): The "Listen Now" URL of the book.
            download_path (str): Folder path to save the book to.

        Returns:
            tuple: (chapter_markers, total_expected_time)
        """
        # Go to book listen page
        self.driver.get(selected_title_link)
        time.sleep(1)

        # Fetch player elements
        chapter_previous = self.driver.find_element(By.CLASS_NAME, 'chapter-bar-prev-button')
        chapter_next = self.driver.find_element(By.CLASS_NAME, 'chapter-bar-next-button')

        toggle_play = self.driver.find_element(By.CLASS_NAME, 'playback-toggle')

        timeline_length = self.driver.find_element(By.CLASS_NAME, 'timeline-end-minutes').find_element(By.CLASS_NAME, 'place-phrase-visual')
        timeline_current_time = self.driver.find_element(By.CLASS_NAME, 'timeline-start-minutes').find_element(By.CLASS_NAME, 'place-phrase-visual')

        chapter_table_open = self.driver.find_element(By.CLASS_NAME, 'chapter-bar-title-button')

        # Get chapter metadata
        print("Getting chapters")

        chapter_table_open.click()
        time.sleep(1)

        chapter_markers = {}

        chapter_dialog_table = self.driver.find_element(By.CLASS_NAME, 'chapter-dialog-table')

        chapter_title_elements = chapter_dialog_table.find_elements(By.CLASS_NAME, 'chapter-dialog-row-title')
        chapter_time_elements = chapter_dialog_table.find_elements(By.CLASS_NAME, 'place-phrase-visual')

        chapter_times = []

        for elem in chapter_time_elements:
            if elem.text:
                chapter_times.append(elem.text)
                self.chapter_seconds.append(convert_metadata.to_seconds(elem.text))

        for index, title in enumerate(chapter_title_elements):
            chapter_markers[title.text] = chapter_times[index]
        
        # Close chapter table
        chapter_table_close = self.driver.find_element(By.CLASS_NAME, 'shibui-shield')
        chapter_table_close.click()
        time.sleep(1)

        print("Got chapters")

        # Go to beginning of book timeline
        while chapter_previous.is_enabled():
            chapter_previous.click()
            time.sleep(.1)
        time.sleep(1)

        expected_time = timeline_length.get_attribute("textContent").replace("-", "")
        print(f"Final book should be ~{expected_time} in length.")


        # Download part files
        print("Getting files")

        mp3_urls = self.requests_to_mp3_files()
        loaded_duration = 0
        current_location = 0
        part_num = 1
        expected_duration = convert_metadata.to_seconds(expected_time)
        self.chapter_seconds.append(expected_duration)

        # Main loop for walking through book
        while True:
            # Collect available urls, and download next part; this also detects
            # loop end when audio is complete.
            mp3_urls = self.requests_to_mp3_files()
            url = mp3_urls.get(f"{part_num:02d}")
            if url:
                length = overdrive_download.download_mp3_part(url, f"{part_num:02d}", download_path, self.get_cookies())
                # If valid download, add the length of the part to the total, check progress through whole book
                if length:
                    loaded_duration += length
                    print(f"{loaded_duration:.2f}/{expected_duration:.2f} sec  -  {loaded_duration/expected_duration*100:.2f}%")
                    if loaded_duration >= expected_duration-1:
                        print("Downloaded complete audio")
                        print(f"Book contained {part_num} part(s)")
                        break
                    part_num += 1
                    continue
                else:
                    print(f"Download failed for part {part_num}")
                    sys.exit(3)

            # Begin search for the absent part.
            lower_bound = int(loaded_duration)
            # Get the marker for the chapter AFTER the biggest duration. (This
            # will be the end of the book if we go past that.)
            upper_bound = self.chapter_seconds[1 + self.chapter_containing(loaded_duration + 60*60)]
            print(f"Missing part {part_num} between ({lower_bound}, {upper_bound}) sec")
            old_upper_bound = None
            collapse_detected = False
            while not self.has_url(part_num):
                current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))

                # Require progress on each iteration.
                if upper_bound == old_upper_bound:
                    # One last effort.
                    old_loc = current_location
                    span = upper_bound - lower_bound
                    print(f"Using play toggle between {lower_bound}, {upper_bound} ({span}s), start at {current_location}")
                    try:
                        toggle_play.click()
                        one_try = False
                        while one_try or (not self.has_url(part_num) and old_loc+span > current_location):
                            time.sleep(1)
                            one_try = True
                            current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                    finally:
                        toggle_play.click()
                    if self.has_url(part_num):
                        print(f"Found part by using play toggle between {lower_bound}, {upper_bound}")
                        continue
                    raise Exception(f"Need more precise search for {upper_bound - lower_bound}s range between {lower_bound}, {upper_bound}")
                old_upper_bound = upper_bound

                # Handle a "collapse" (lower==upper) by trying to search the whole book.
                if not collapse_detected and lower_bound == upper_bound:
                    print(f"Could not find part {part_num}, retrying by searching whole book.")
                    upper_bound = self.chapter_seconds[-1]
                    collapse_detected = True

                # First, see if there's a chapter mark that divides our range.
                desired_chapter = self.chapter_containing(upper_bound)
                desired_chapter_start = self.chapter_seconds[desired_chapter]
                current_chapter = self.chapter_containing(current_location)
                current_chapter_start = self.chapter_seconds[current_chapter]
                if desired_chapter_start >= lower_bound and desired_chapter_start != current_location:
                    offset = current_location - current_chapter_start
                    low, high = sorted([current_chapter, desired_chapter])
                    span = desired_chapter_start - current_location
                    print(f"Skipping from chapter {current_chapter} + {offset}s to {desired_chapter}, span {span}s. Chs: {self.chapter_seconds[low:high+1]}")

                    chapter_table_open.click()
                    time.sleep(1)

                    chapter_title_elements = self.driver.find_elements(By.CLASS_NAME, 'chapter-dialog-row-title')

                    for index, title in enumerate(chapter_title_elements):
                        # Go to the beginning of the chapter we need, or the
                        # last chapter if we're trying to get to the end.
                        if index == desired_chapter or (index == len(chapter_title_elements) - 1 and upper_bound == expected_duration):
                            title.click()
                            break

                    # Close chapter table
                    chapter_table_close = self.driver.find_element(By.CLASS_NAME, 'shibui-shield')
                    chapter_table_close.click()
                    time.sleep(1)

                    if upper_bound == expected_duration:
                        # Can get to the end of the audio with one more click.
                        chapter_next.click()
                        time.sleep(1)
                        continue

                    current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                    if current_location != desired_chapter_start:
                        # This is just a sanity check, caught some errors once though.
                        current_chapter = self.chapter_containing(current_location)
                        current_chapter_start = self.chapter_seconds[current_chapter]
                        raise Exception(f"failed to find start of chapter {desired_chapter}, actually ch{current_chapter} + {current_location - current_chapter_start}")
                    # If there's an internal split, it gives us a new upper bound.
                    if not self.has_url(part_num) and lower_bound < current_location <= upper_bound:
                        print(f"No URL for {part_num} at {upper_bound}, reducing to {current_location-1}.")
                        upper_bound = current_location - 1
                if self.has_url(part_num):
                    continue
                # Next, try to use the minute-skip key to get into the range.
                body = self.driver.find_element(By.TAG_NAME, "body")
                old_location = current_location
                while current_location <= lower_bound and current_location <= upper_bound-60 and not self.has_url(part_num):
                    # ffwd into the range if you can, without going past it.
                    body.send_keys(Keys.PAGE_DOWN)
                    time.sleep(.5)
                    current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                while current_location-60 > lower_bound and not self.has_url(part_num):
                    # frewind back to near the start of the range, without going past it.
                    body.send_keys(Keys.PAGE_UP)
                    time.sleep(.5)
                    current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                if self.has_url(part_num):
                    # Shortcut if we're done.
                    continue
                if old_location != current_location:
                    dir = "forward" if old_location < current_location else "backward"
                    mins = abs(old_location - current_location) / 60
                    print(f"Skipped {dir} {mins:.2f} mins")
                if not self.has_url(part_num) and lower_bound < current_location <= upper_bound:
                    print(f"No URL for {part_num} at {upper_bound}, reducing to {current_location-1}.")
                    upper_bound = current_location - 1
                # Next, try to use the small-skip key to get into the new range.
                old_location = current_location
                while current_location <= lower_bound and current_location <= upper_bound-15 and not self.has_url(part_num):
                    # fwd into the range if you can, without going past it.
                    body.send_keys(Keys.ARROW_RIGHT)
                    time.sleep(.5)
                    current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                while current_location-15 > lower_bound and not self.has_url(part_num):
                    # rewind back to near the start of the range, without going past it.
                    body.send_keys(Keys.ARROW_LEFT)
                    time.sleep(.5)
                    current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                if self.has_url(part_num):
                    continue
                if old_location != current_location:
                    dir = "forward" if old_location < current_location else "backward"
                    mins = abs(old_location - current_location)
                    print(f"Skipped {dir} {mins}s")
                if not self.has_url(part_num) and lower_bound < current_location <= upper_bound:
                    print(f"No URL for {part_num} at {upper_bound}, reducing to {current_location-1}.")
                    upper_bound = current_location - 1

        # Attempt to find and save cover image
        cover_image_url = next(
            (req.url for req in self.driver.requests if req.response and '.jpg' in req.url and 'listen.overdrive.com' in req.url),
            None
        )

        cover_path = os.path.abspath(os.path.join(download_path, "cover.jpg"))
        if overdrive_download.download_cover(cover_image_url, cover_path, self.get_cookies(), self.config.get("abort_on_warning", False)):
            print("Downloaded cover")

        return (chapter_markers, expected_time)
