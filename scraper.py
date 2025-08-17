from typing import Tuple
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
from convert_metadata import to_hms
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
        if not self.driver:
            raise Exception("Driver not initialized")

        self.driver.get(self.base_url + "/account/ozone/sign-in")

        # Dismiss cookie banner if present
        banners = self.driver.find_elements(By.CLASS_NAME, 'cookie-banner-close-button')
        if banners: banners[0].click()

        # Enter credentials
        sublibrary_inputs = self.driver.find_elements(By.ID, 'signin-options')
        sublibrary_input = sublibrary_inputs[0] if len(sublibrary_inputs) == 1 else None

        wait = WebDriverWait(self.driver, timeout=15)

        # Logins with sublibrary sometimes require choosing it first.
        if sublibrary_input and sublibrary_input.is_displayed() and sublibrary_input.is_enabled():
            interactive = not self.config.get('sublibrary')
            sublibrary_input.click()
            time.sleep(0.25)
            sublibrary_output = self.driver.find_element(By.CLASS_NAME, 'ui-autocomplete')
            print(f"Starting with {len(sublibrary_output.find_elements(By.TAG_NAME, 'li'))} sublibrary options.")
            if interactive:
                subs = sublibrary_output.find_elements(By.TAG_NAME, 'li')
                # Display numbered list of sublibraries and prompt for selection
                for index,sub in enumerate(subs):
                    print(f"   {index}: {sub.text}")
                sub_index = int(input("Select sublibrary: "))
                subs[sub_index].click()
            else:
                # Type one key at a time until selection list reduces to a single option
                for char in self.config['sublibrary']:
                    sublibrary_input.send_keys(char)
                    time.sleep(0.1)
                    subs = sublibrary_output.find_elements(By.TAG_NAME, 'li')
                    print(f"   after typing '{char}': {len(subs)} options.")
                    # If only one ul item left, select it
                    if len(subs) == 1:
                        sublibrary_output = self.driver.find_element(By.CLASS_NAME, 'ui-autocomplete')
                        subs = sublibrary_output.find_elements(By.TAG_NAME, 'li')
                        subs[0].click()
                        time.sleep(0.25)
                        break
                    elif not subs:
                        print(f"ERROR: Sublibrary {self.config['sublibrary']} not found in library {self.config['library']}")
                        sys.exit(2)

        signin_button = self.driver.find_element(By.CLASS_NAME, 'signin-button')

        wait.until(lambda _ : signin_button.is_enabled())

        username_input = self.driver.find_element(By.ID, 'username')
        password_input = self.driver.find_element(By.ID, 'password')
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
                    # Check for site cookie domain, case insensitive (we keep all cookies in same file)
                    if self.config['library'].lower() in cookie['domain'].lower():
                        self.driver.add_cookie(cookie)
            except:
                print("Invalid cookies")
                return self._login()

        # Go to authenticated page to test if cookies are still valid
        self.driver.get(self.base_url + "/account/loans")

        loans_titles = self.driver.find_elements(By.CLASS_NAME, 'account-title')
        if loans_titles:
            if "Loans" in loans_titles[0].text:
                # Already have valid session
                return cookies
        else:
            return self._login()

    def get_loans(self):
        """
        Retrieves all current audiobook loans for the user.

        Returns:
            list: List of dictionaries with book info: title, author, link, and ID.
        """
        print("Finding books...")
        if not self.driver:
            raise Exception("Driver not initialized")

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
            title_element = block.find_element(By.CLASS_NAME, 'title-name')
            author_element = block.find_element(By.CLASS_NAME, 'title-author')
            listen_links = block.find_elements(By.PARTIAL_LINK_TEXT, 'Listen now')
            listen_link = book_id = None
            # Parse cautiously, other media types can be checked out but we don't get them.
            if listen_links:
                if listen_link := listen_links[0].get_attribute('href'):
                    book_id = listen_link.split('/')[-1]
            if not book_id:
                print(f"Book at index {index} has no listen link, may not be audiobook: {title_element.text.strip()}")
                continue

            books.append({"index": index, "title": title_element.text.strip(), "author": author_element.text.strip(), "link": listen_link, "id": book_id})

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

    def closest_chapter_mark(self, lower_bound: int, upper_bound: int, current_location: int) -> Tuple[Tuple[int, int]|None, int]:
        """
            Finds the closest chapter mark to reach into the range near the lower bound.

            Args:
                lower_bound (int): Lower bound of the chapter marks.
                upper_bound (int): Upper bound of the chapter marks.
                current_location (int): Current location in the book.
        """
        current_chapter = self.chapter_containing(current_location)
        earliest_chapter = self.chapter_containing(lower_bound)
        mid_chapter = self.chapter_containing(lower_bound) + 1
        ending_chapter = self.chapter_containing(upper_bound) + 1
        # Best case: there's an easy chapter mark cutting the range in half.
        if current_chapter < mid_chapter < ending_chapter:
            return (mid_chapter, self.chapter_seconds[mid_chapter]), current_chapter
        # No easy chapter mark. We will assess three distances:
        # 1. Earliest chapter start to lower bound
        earliest_chapter_start = self.chapter_seconds[earliest_chapter]
        earliest_distance = abs(lower_bound - earliest_chapter_start)

        # 2. Ending chapter start to lower bound
        ending_chapter_start = self.chapter_seconds[ending_chapter]
        ending_distance = abs(lower_bound - ending_chapter_start)

        # 3. Current location to lower bound
        current_distance = abs(lower_bound - current_location)
        # Simple but sad case: no chapter jump will help.
        if current_distance <= earliest_distance and current_distance <= ending_distance:
            return None, current_chapter

        # Otherwise, choose the chapter that's closest to the lower bound.
        desired_chapter = earliest_chapter if earliest_distance <= ending_distance else ending_chapter
        return (desired_chapter, self.chapter_seconds[desired_chapter]), current_chapter

    def get_book(self, selected_title_link: str, download_path: str) -> list[Tuple[int, int]]:
        """
        Downloads the selected audiobook and associated metadata.

        Args:
            selected_title_link (str): The "Listen Now" URL of the book.
            download_path (str): Folder path to save the book to.

        Returns:
            chapter_markers
        """
        if not self.driver:
            raise Exception("Driver is not initialized")

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

        # Allow debugging if one or more fails to fetch. Also turns off "may be None" warnings.
        fetched = [chapter_previous, chapter_next, toggle_play, timeline_length, timeline_current_time, chapter_table_open]
        if None in fetched:
            raise Exception(f"Failed to fetch one or more player elements: {fetched}")

        # Get chapter metadata
        print("Getting chapters")

        chapter_table_open.click()
        time.sleep(1)

        chapter_markers = []

        chapter_dialog_table = self.driver.find_element(By.CLASS_NAME, 'chapter-dialog-table')
        if not chapter_dialog_table:
            raise Exception("Failed to find chapter dialog table")

        chapter_title_elements = chapter_dialog_table.find_elements(By.CLASS_NAME, 'chapter-dialog-row-title')
        chapter_time_elements = chapter_dialog_table.find_elements(By.CLASS_NAME, 'place-phrase-visual')

        if not chapter_title_elements:
            raise Exception("Failed to find chapter title elements")
        if not chapter_time_elements:
            raise Exception("Failed to find chapter time elements")

        chapter_times = []
  
        mp3_urls = self.requests_to_mp3_files()
        current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))

        for elem in chapter_time_elements:
            if elem.text:
                chapter_times.append(elem.text)
                self.chapter_seconds.append(convert_metadata.to_seconds(elem.text))

        for index, title in enumerate(chapter_title_elements):
            if index == 0:
                title.click()
            # The end of each chapter is the start of the next.
            end = self.chapter_seconds[index+1] if index+1 < len(self.chapter_seconds) else None
            chapter_markers.append( (title.text, chapter_times[index], end) )
        
        # Close chapter table
        chapter_table_close = self.driver.find_element(By.CLASS_NAME, 'shibui-shield')
        chapter_table_close.click()
        time.sleep(1)

        print(f"Got {len(chapter_times)} chapters")

        expected_time = timeline_length.get_attribute("textContent").replace("-", "")
        print(f"Final book should be ~{expected_time} in length.")

        if chapter_markers:
            # Modify the last chapter marker to end at the end of the book.
            title, start, _ = chapter_markers.pop()
            end = expected_time
        else:
            # Book has no chapters, give it a fake one.
            title, start, end = None, "0:0:0", expected_time
        chapter_markers.append( (title, start, end) )

        expected_duration = convert_metadata.to_seconds(expected_time)
        self.chapter_seconds.append(expected_duration)

        print("Getting chapter:part structure.")

        # Initialize part 1 always in chapter 0.
        chapter_to_part = {0:1}
        seen_parts = {1}

        # Add the chapter the ereader started up in.
        ch = self.chapter_containing(current_location)
        parts = set(int(k) for k in mp3_urls.keys()) - seen_parts
        if parts:
            chapter_to_part[ch] = min(parts)
        seen_parts.update(parts)

        # Partition the book by skimming through chapters and observing known parts.
        print(f"Building structure chapter:part ({len(self.chapter_seconds)} chapters):", end='')
        needs_end = True
        for ch in range(len(self.chapter_seconds)):
            print(f" {ch}", end='', flush=True)
            parts = set(int(k) for k in self.requests_to_mp3_files()) - seen_parts
            if chapter_to_part.get(ch) is None and parts:
                chapter_to_part[ch] = min(parts)
            seen_parts.update(parts)
            if chapter_next.is_enabled():
                chapter_next.click()
                time.sleep(0.5)
            else:
                needs_end = False
        print() # finish the above progress bar.

        # Find the end of the book, including any trailing 'parts'.
        trailing_parts = []
        current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
        if not needs_end:
            p = max(seen_parts) if seen_parts else None
            print(f"Found end of book at end of chapter {ch}, part {p}, at {to_hms(current_location)}")
        else:
            print(f"Did not find end of book, at {to_hms(current_location)}, digging deeper...")
            skips = 0
            old_location = current_location
            while chapter_next.is_enabled():
                chapter_next.click()
                time.sleep(0.5)
                skips += 1
            current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
            parts = set(int(k) for k in self.requests_to_mp3_files()) - seen_parts
            if skips or parts:
                if parts:
                    trailing_parts = parts
                # This isn't terrible, we've found a lot of parts that will be fetched.
                print(f"WARNING: {skips} chapters and parts {parts} NOT IN TABLE OF CONTENTS, from {to_hms(old_location)} to {to_hms(current_location)} (diff {to_hms(current_location - old_location)})")

        # Invert the table of chapters to parts, to get a table where given the
        # part we find which chapter to flip to: either the exact chapter, or
        # the upper bound for its search (the uppoer bound is used because the
        # lower bound will change as we find more parts).
        part_to_chapter = {chapter_to_part[0]:0}
        last_seen = chapter_to_part[0]
        for ch, part in sorted(chapter_to_part.items()):
            if ch == 0:
                continue
            # ch is the chapter exactly where 'part' is found.
            for intermediate_pt in range(last_seen+1, part):
                # often we don't see every part, so we fill in the gaps.
                part_to_chapter[intermediate_pt] = ch - 1
            last_seen = part
            part_to_chapter[part] = ch
        past_end = max(part_to_chapter.values()) + 1
        for part in trailing_parts:
            part_to_chapter[part] = past_end

        print("Got part->chapter structure:",
              [f"{part:02d}->{ch} ({to_hms(self.chapter_seconds[ch]) if ch < len(self.chapter_seconds) else '??:??'})"
              for part, ch in part_to_chapter.items() ]
              )

        # Download part files
        print("Getting files")
        current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
        loaded_duration = convert_metadata.get_total_duration(download_path)
        part_num = 1

        # Check for resumable part files.
        print("Checking for resumable parts.")
        tmp_dir = download_path
        if loaded_duration:
            parts = [f"part{part_num:02d}.mp3" for part_num in range(1, max(part_to_chapter)+1)]

            # Check that the dir contains sequential part files.
            resumable_parts = [part for part in parts if os.path.isfile(os.path.join(tmp_dir, part))]
            if not resumable_parts or resumable_parts != parts[:len(resumable_parts)]:
                print(f"ERROR: tmp folder contains corrupted download (check numbered parts), please remove or clean up: {tmp_dir}")
                print(resumable_parts)
                sys.exit(1)
            resumable_parts = [fullname for part in parts if os.path.isfile(fullname := os.path.join(tmp_dir, part))]

            # Sum the durations of the resumable parts.
            exact_size = 0.0
            for _, fullname in enumerate(resumable_parts, 1):
                this_size = convert_metadata.get_mp3_duration(fullname)
                exact_size += this_size

            # Check that the dir doesn't have any other media files (duration
            # range accounts for inexactness).
            if not loaded_duration - 10 < exact_size < loaded_duration + 10:
                print(f"ERROR: tmp folder contains {to_hms(loaded_duration)} duration media files when expected {to_hms(int(exact_size))}, please remove or clean up: {tmp_dir}")
                sys.exit(1)
            part_num = len(resumable_parts) + 1
            print(f"Resuming download from {part_num} part(s) at {to_hms(loaded_duration)}")

        # Main loop for walking through book
        while loaded_duration < expected_duration-1:
            # Collect available urls, and download next part; this also detects
            # loop end when audio is complete.
            mp3_urls = self.requests_to_mp3_files()
            url = mp3_urls.get(f"{part_num:02d}")
            if url:
                length = overdrive_download.download_mp3_part(url, part_num, download_path, self.get_cookies())
                # If valid download, add the length of the part to the total, check progress through whole book
                if length:
                    # Use ground truth from metadata rather than adding approximations
                    loaded_duration = convert_metadata.get_total_duration(download_path)
                    print(f"{to_hms(loaded_duration)} / {to_hms(expected_duration)} - {loaded_duration}/{expected_duration} sec  -  {loaded_duration/expected_duration*100.0:.2f}%")
                    part_num += 1
                    continue
                else:
                    print(f"Download failed for part {part_num}")
                    sys.exit(3)

            # Begin search for the absent part.
            lower_bound = int(loaded_duration)
            # Look up the upper bound in our table (we start at the end of the given chapter)
            if part_num in part_to_chapter:
                upper_bound = self.chapter_seconds[1 + part_to_chapter[part_num]]
            else:
                upper_bound = expected_duration
            # Clip the upper bound to a maximum of 3 hours, should be longer
            # than any reasonable part length. The algorithm will "collapse"
            # upper and lower bounds if that isn't true, we'll detect that
            # later.
            if upper_bound - lower_bound > 3*60*60:
                upper_bound = lower_bound + 3*60*60

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
                    print(f"Using play toggle between {to_hms(lower_bound)}, {to_hms(upper_bound)} ({span}s), start at {current_location}")
                    first_try = True
                    try:
                        toggle_play.click()
                        while first_try or (not self.has_url(part_num) and old_loc+span > current_location):
                            time.sleep(5 if first_try else 1)
                            current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                            if not first_try and not current_location > old_loc:
                                print(f"Play toggle might not be responding, location was {to_hms(old_loc)}, now {to_hms(current_location)}")
                            first_try = False
                    finally:
                        if first_try:
                            time.sleep(5)
                        toggle_play.click()
                    if self.has_url(part_num):
                        print(f"Found part by using play toggle between {lower_bound}, {upper_bound}")
                        continue
                    print(f"Need more precise search for {upper_bound - lower_bound}s range between {to_hms(lower_bound)}, {upper_bound}")
                    raise Exception(f"Need more precise search for {upper_bound - lower_bound}s range between {lower_bound}, {upper_bound}")
                old_upper_bound = upper_bound

                # Handle a "collapse" (lower==upper) by trying to search the whole book.
                if not collapse_detected and lower_bound == upper_bound:
                    print(f"Could not find part {part_num}, retrying by searching whole book.")
                    upper_bound = self.chapter_seconds[-1]
                    collapse_detected = True

                # First, see if there's a chapter mark that is closer to our
                # range than the current location.
                chapter_move, current_chapter = self.closest_chapter_mark(lower_bound, upper_bound, current_location)
                if chapter_move:
                    desired_chapter, desired_chapter_start = chapter_move
                    span = desired_chapter_start - current_location
                    print(f"Skipping from chapter {current_chapter} to {desired_chapter}/{len(self.chapter_seconds)-1}, span {span}s.")

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

                    current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))
                    current_chapter = self.chapter_containing(current_location)
                    current_chapter_start = self.chapter_seconds[current_chapter]

                    # Sometimes the player dumps us in the middle of a chapter, so go back if optimal.
                    if current_location > current_chapter_start:
                        print(f"Player dumped us in the middle of a chapter, going back {current_location-current_chapter_start}s.")
                        chapter_previous.click()
                        time.sleep(1)
                        current_location = convert_metadata.to_seconds(timeline_current_time.get_attribute("textContent"))

                    if self.has_url(part_num):
                        continue
                    elif lower_bound <= current_location < upper_bound:
                        # Check for a possibly fuzzy lower_bound, mp3 sometimes is a few seconds off.
                        if lower_bound <= current_location <= lower_bound + 15:
                            lower_bound = current_location + 1
                        else:
                            # If there's an internal split, it gives us a new upper bound.
                            print(f"No URL for {part_num} at {current_location}, reducing to {current_location-1}.")
                            upper_bound = current_location - 1
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

        if loaded_duration >= expected_duration-1:
            print("Downloaded complete audio")
            print(f"Book contained {part_num-1} part(s)")

        # Attempt to find and save cover image
        cover_image_url = next(
            (req.url for req in self.driver.requests if req.response and '.jpg' in req.url and 'listen.overdrive.com' in req.url),
            None
        )

        cover_path = os.path.abspath(os.path.join(download_path, "cover.jpg"))
        if overdrive_download.download_cover(cover_image_url, cover_path, self.get_cookies(), self.config.get("abort_on_warning", False)):
            print("Downloaded cover")

        return chapter_markers

