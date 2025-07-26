"""
ODMPY-NG: OverDrive audiobook download and conversion tool
"""

import argparse
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
def parse_book_selection_input(userinput: str, books: list) -> list[int]:
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
            parts = part.split('-')
            if all(part.isdigit() for part in parts):
                start, end = map(int, part.split('-'))
                parts_set.update(range(start, end+1))
            else:
                raise ValueError(f"Invalid range input: {part}")
        else:
            if part.isdigit():
                parts_set.add(int(part))
            else:
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

    # Command line parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", type=str, help="Path to config file")
    parser.add_argument("--id", "-i", type=int, help="Libby ID for a single book to download")
    parser.add_argument("--retry", "-r", action="store_true", help="Allow retry of stopped downloads (if left in tmp dir)")
    parser.add_argument("--name-dir", "-n", type=str, help="Fixed subdirectory relative to /downloads to move single downloaded book to")
    # These two are mutually exclusive
    exclusive_group = parser.add_mutually_exclusive_group(required=False)
    exclusive_group.add_argument("--library", "-L", type=int, help="Index of library within config to download from")
    exclusive_group.add_argument("--site-id", "-s", type=int, help="Site-Id assigned in config to library to download from")
    args = parser.parse_args()

    if not os.path.exists(args.config_file):
        print(f"Error: Config file '{args.config_file}' not found")
        sys.exit(1)

    config_file = args.config_file
    if os.path.isfile(config_file):
        with open(config_file) as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                print(f"Error: Config file '{config_file}' is not valid JSON")
                sys.exit(1)    
    else:
        print(f"Error: Config file '{config_file}' not found")
        sys.exit(1)    

    config_dir = os.path.dirname(config_file)
    if not os.path.exists(config_dir):
        print(f"Error: Config directory '{config_dir}' not found")
        sys.exit(1)

    downloads_dir = pathlib.Path("/downloads")
    tmp_base = pathlib.Path("/tmp-downloads")
    tmp_base.mkdir(parents=True, exist_ok=True)

    cookies = []
    cookie_file = os.path.join(config_dir, "cookies")
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file) as f:
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

    # Enforce unique site-ids in libraries (except None is fine)
    site_ids = [s for library in libraries if (s := library.get("site-id")) is not None]
    if len(site_ids) != len(set(site_ids)):
        print(f"Error: site-ids must be unique within libraries, please edit {config_file}")
        sys.exit(1)

    library_index = None
    print("\nAvailable libraries:")
    for i, library in enumerate(libraries):
        visible_marker = "    "
        if args.library is not None:
            if i == args.library:
                visible_marker = " -> "
                library_index = i
        elif args.site_id is not None:
            if library.get("site-id") == args.site_id:
                visible_marker = " -> "
                library_index = i
        else:
            visible_marker = f"{i:>3}:"
        print(f"{visible_marker} {library['name']} - {library['url']}")

    if library_index is None and args.library is not None:
        print(f"Error: Library {args.library} not found in config")
        sys.exit(1)
    if library_index is None and args.site_id is not None:
        print(f"Error: Library matching site-id {args.site_id} not found in config")
        sys.exit(1)

    if len(libraries) == 1:
        # Only one library, automatically select it
        library_index = 0
    elif library_index is None:
        # Let user select which library to use
        library_text = input("\nSelect a library to use: ")
        if not library_text:
            sys.exit(0) # Easy polite exit
        elif not library_text.isdigit():
            library_index = None
        library_index = int(library_text)
 
    if library_index is None or library_index < 0 or library_index >= len(libraries):
        print("Invalid library selection")
        sys.exit(1)

    # Create a compatible config object for the scraper
    selected_library = libraries[library_index]
    scraper_config = {
        "library": selected_library["url"],
        "user": selected_library["card_number"],
        "pass": selected_library["pin"],
        "tmp-dir": None, # to be filled in later
        "allow-retry": args.retry,
        "id": args.id,
    }
    os.makedirs(downloads_dir, mode=0o755, exist_ok=True)
        
    print(f"Using library: {selected_library['name']}")

    scraper = Scraper(scraper_config)
    cookies = scraper.ensure_login(cookies)

    if not cookies:
        print("Sign in failed")
        sys.exit(1)

    with open(cookie_file, "w") as f:
        json.dump(cookies, f, indent=4)

    # Collect list of loans
    books = scraper.get_loans() # [{"index": 0, "title": "", "author": "", "link": "", "id": 0}]

    # Print loans for selection by user
    title_selections = []

    find_id = str(scraper_config["id"]) if scraper_config["id"] else ''
    for book in books:
        this_one = False
        if book["id"] == find_id:
            title_selections.append(book["index"])
            this_one = True

        visible_marker = "->" if this_one else "  "
        print(f"{visible_marker} {book['index']}: {book['title']} - {book['author']} ({book['id']})")

    if not title_selections:
        selections_input = input("Select a title to download (e.g., 0,1,2-3): ")
        title_selections = parse_book_selection_input(selections_input, books)

    if args.name_dir and len(title_selections) > 1:
        print("ERROR: Cannot use --name-dir with multiple books")
        sys.exit(1)

    # For each selected book, get the data
    for title_index in title_selections:
        # Get book selection from index
        book_selection = get_book_by_index(title_index, books)
        if not book_selection:
            print(f"ERROR: Invalid book selection, should not happen: {title_index}")
            continue

        # Create tmp directory with absolute path, one for each book.
        tmp_dir = tmp_base / book_selection["id"]
        scraper_config["tmp-dir"] = str(tmp_dir)
        if os.path.exists(tmp_dir) and not scraper_config.get("allow-retry"):
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        print(f"Accessing {book_selection['title']}, ID: {book_selection['id']}")

        # Use scraper.py to download book
        book_data = scraper.get_book(book_selection["link"], tmp_dir)

        if not book_data:
            print("Failed to download")
            continue

        # Reformat returned tuple for easier readability
        book_title = book_selection["title"]
        book_author = book_selection["author"]
        book_chapter_markers, book_expected_length = book_data

        # Save current cookies for upcoming downloads
        cookies = scraper.get_cookies()
        filter_table = str.maketrans(dict.fromkeys(string.punctuation))

        if args.name_dir:
            download_path = os.path.abspath(os.path.join(downloads_dir, args.name_dir))
        else:
            # Filter to remove punctuation from book title/author for file path
            download_path = os.path.abspath(os.path.join(
                downloads_dir, 
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

            sanitized_title = book_title.translate(filter_table).replace(" ", "")
            output_file = os.path.abspath(os.path.join(download_path, sanitized_title + ".m4b"))

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
