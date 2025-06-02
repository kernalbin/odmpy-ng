"""
ODMPY-NG: OverDrive audiobook download and conversion tool
"""

import json
import os
import string
import shutil
import sys
import pathlib
import ffmetadata
from scraper import Scraper
import overdrive_download
import file_conversions
import convert_metadata

# Convert user entered string into a list of valid book indexes
# Allows for comma separated items and dash separated ranges
def parse_book_selection_input(userinput: str, books: list) -> set:
    """
    Parses a comma-separated and range-based string into a list of valid book indexes.

    Args:
        userinput (str): String input from user selecting books.
        books (list): Complete list of books to validate against

    Returns:
        set: Parsed ordered list of selected books
    """
    parts_set = set()
    parts = userinput.split(',')

    valid_indexes = {book["index"] for book in books}

    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                parts_set.update(range(start, end+1))
            except ValueError:
                raise ValueError(f"Invalid range input: {part}")
        else:
            try:
                parts_set.add(int(part))
            except ValueError:
                raise ValueError(f"Invalid integer input: {part}")
            
    return sorted(parts_set.intersection(valid_indexes))

def get_book_by_index(index: int, books: list):
    """
    Retrieves a book dictionary by index from a list of books.

    Args:
        index (int): Index in book list
        books (list): Complete list of books to search

    Returns:
        dict: Book info for given index
    """
    return next((b for b in books if b["index"] == index), None)

def main():

    print("Starting ODMPY-NG")

    if len(sys.argv) < 2:
        print("Error: Config file path is required")
        print("Usage: python interactive.py <config_file_path>")
        sys.exit(1)

    config_file = sys.argv[1]
    try:
        with open(config_file) as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file '{config_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Config file '{config_file}' is not valid JSON")
        sys.exit(1)    

    cookies = []
    if os.path.exists("cookies"):
        try:
            with open("cookies") as f:
                cookies = json.load(f)
        except Exception as e:
            print(f"Error loading cookies: {e}")

    print("Config loaded")

    if config.get("low_quality_encode", 0):
        print("WARNING: Low quality mode set, 32k audio encodes.")

    libraries = config.get("libraries", [])
    if not libraries:
        print("No libraries found, did you create a valid config file?")
        sys.exit(1)

    print("\nAvailable libraries:")
    for i, library in enumerate(libraries):
        print(f"{i}: {library['name']} - {library['url']}")

    if len(libraries) == 1:
        # Only one library, automatically select it
        library_index = 0
    else:
        # Let user select which library to use
        library_index = int(input("\nSelect a library to use: "))
        
    if library_index < 0 or library_index >= len(libraries):
        print("Invalid library selection")
        sys.exit(1)
        
    # Create a compatible config object for the scraper
    selected_library = libraries[library_index]
    scraper_config = {
        "library": selected_library["url"],
        "user": selected_library["card_number"],
        "pass": selected_library["pin"],
        "download-dir": '/downloads'
    }
        
    print(f"Using library: {selected_library['name']}")


    scraper = Scraper(scraper_config)
    cookies = scraper.ensure_login(cookies)

    if not cookies:
        print("Sign in failed")
        sys.exit(1)

    with open("cookies", "w") as f:
        json.dump(cookies, f, indent=4)

    # Collect list of loans
    books = scraper.get_loans() # [{"index": 0, "title": "", "author": "", "link": "", "id": 0}]

    # Print loans for selection by user
    for book in books:
        print(f"{book["index"]}: {book["title"]} - {book["author"]}")

    selections_input = input("Select a title to download (e.g., 0,1,2-3): ")
    title_selections = parse_book_selection_input(selections_input, books)

    # For each selected book, get the data
    for title_index in title_selections:
        # Create tmp directory with absolute path
        tmp_dir = os.path.abspath(os.path.join(os.getcwd(), "tmp"))
        os.makedirs(tmp_dir, mode=0o755, exist_ok=True)

        # Get book selection from index
        book_selection = get_book_by_index(title_index, books)
        print(f"Accessing {book_selection["title"]}, ID: {book_selection["id"]}")

        # Use scraper.py to download book
        book_data = scraper.get_book(book_selection["link"], tmp_dir) # (chapter_markers, expected_time)

        if not book_data:
            print("Failed to download")
            continue

        # Reformat returned tuple for easier readability
        book_title = book_selection["title"]
        book_author = book_selection["author"]
        book_chapter_markers, book_expected_length = book_data

        # Save current cookies for upcoming downloads
        cookies = scraper.get_cookies()

        # Filter to remove punctuation from book title/author for file path
        filter_table = str.maketrans(dict.fromkeys(string.punctuation))
        download_path = os.path.abspath(os.path.join(
            scraper_config["download-dir"], 
            book_author.translate(filter_table), 
            book_title.translate(filter_table)
        ))

        os.makedirs(download_path, exist_ok=True)


        if config.get("download_thunder_metadata", 0) or config.get("convert_audiobookshelf_metadata", 0):
            # Both of these require thunder metadata.
            metadata_path = os.path.abspath(os.path.join(download_path, 'info.json'))
            chapters_path = os.path.abspath(os.path.join(download_path, 'chapters.json'))
            with open(chapters_path, 'w') as f:
                json.dump(book_chapter_markers, f)
            if overdrive_download.download_thunder_metadata(book_selection["id"], metadata_path):
                print("Downloaded json metadata")
                if config.get("convert_audiobookshelf_metadata", 0):
                    convert_metadata.convert_file(metadata_path, book_expected_length)
                    print("Provided audiobookshelf metadata")
                    if not config.get("download_thunder_metadata", 0):
                        os.unlink(metadata_path)
                        os.unlink(chapters_path)
                        print("Cleaned up json metadata")


        if config.get("skip_reencode", 0):
            # Just copy everything to the dest.
            source, dest = pathlib.Path(tmp_dir), pathlib.Path(download_path)
            for p in source.iterdir():
                shutil.copy(p, dest)
        else:
            if file_conversions.encode_aac_multiprocessing(tmp_dir, tmp_dir, config.get("low_quality_encode", 0), config.get("encoder_count", 4)):
                print("Converted all files to AAC M4B")

            if file_conversions.concat_m4b(tmp_dir, tmp_dir, 'temp.m4b'):
                print("Converted to single M4B")

            print("Generating metadata")
            ffmetadata.write_metafile(tmp_dir, book_chapter_markers, book_title, book_author, book_expected_length)
            
            print("Adding metadata to audiobook")
            cover_path = os.path.abspath(os.path.join(tmp_dir, "cover.jpg"))

            output_file = os.path.abspath(os.path.join(download_path, book_title.replace(" ", "")+".m4b"))
            
            if file_conversions.encode_metadata(tmp_dir, "temp.m4b", output_file, "ffmetadata", cover_path):
                print("Finished file created")
                # Clean up temporary files
                try:
                    shutil.rmtree(tmp_dir)
                    print("Temporary files cleaned up")
                except Exception as e:
                    print(f"Warning: Could not remove temporary directory: {e}")

    del scraper

if __name__ == "__main__":
    main()