import json, os, string, shutil, sys, pathlib
import ffmetadata
from scraper import Scraper
import overdrive_download
import file_conversions
import convert_metadata

# Convert user entered string into a list of valid book indexes
# Allows for comma separated items and dash separated ranges
def parse_input(input_str: str, books: list) -> set:
    partsSet = set()
    parts = input_str.split(',')

    valid_indexes = {book["index"] for book in books}

    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                partsSet.update(range(start, end+1))
            except ValueError:
                raise ValueError(f"Invalid range input: {part}")
        else:
            try:
                partsSet.add(int(part))
            except ValueError:
                raise ValueError(f"Invalid integer input: {part}")
            
    filtered_indexes = sorted(partsSet.intersection(valid_indexes))
    return filtered_indexes

# Get book dictionary item with index value from the books list
def get_book_by_index(index: int, books: list) -> str | None:
    return next((b for b in books if b["index"] == index), None)

print("Starting ODMPY-NG")

cookies = []

if len(sys.argv) < 2:
    print("Error: Config file path is required")
    print("Usage: python interactive.py <config_file_path>")
    sys.exit(1)

# Load config file specified in argument
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

# Try to find and import cookies from previous session - probably broken in docker unless you mount the tmp folder
if os.path.exists("cookies"):
    try:
        with open("cookies") as f:
            cookies = json.load(f)
    except Exception as e:
        print(f"Error loading cookies: {e}")
        cookies = []

print("Config loaded")

# Warn about low quality encoding (used for testing to speed up wait)
if config.get("low_quality_encode", 0):
    print("WARNING: Low quality mode set, 32k audio encodes.")

# Handle multiple libraries
if "libraries" in config and len(config["libraries"]) > 0:
    print("\nAvailable libraries:")
    for i, library in enumerate(config["libraries"]):
        print(f"{i}: {library['name']} - {library['url']}")

    if len(config["libraries"]) == 1:
        # Only one library, automatically select it
        library_index = 0
    else:
        # Let user select which library to use
        library_index = int(input("\nSelect a library to use: "))
    
    if library_index < 0 or library_index >= len(config["libraries"]):
        print("Invalid library selection")
        sys.exit(1)
    
    # Create a compatible config object for the scraper
    selected_library = config["libraries"][library_index]
    scraper_config = {
        "library": selected_library["url"],
        "user": selected_library["card_number"],
        "pass": selected_library["pin"],
        "download-dir": '/downloads'
    }
    
    print(f"Using library: {selected_library['name']}")
else:
    print("No libraries found, did you create a valid config file?")
    sys.exit(1)

# Notify of cookies file loaded from previous session
if cookies:
    print("Cookies loaded:")
    print(cookies)

scraper = Scraper(scraper_config)

# Login to the chosen library, and save the cookies to a file.
cookies = scraper.ensureLogin(cookies)

if not cookies:
    print("Sign in failed")
    sys.exit(1)

with open("cookies", "w") as f:
    json.dump(cookies, f, indent=4)

# Collect list of loans
books = scraper.getLoans() # [{"index": 0, "title": "", "author": "", "link": "", "id": 0}]

# Print loans for selection by user
for book in books:
    print(f"{book["index"]}: {book["title"]} - {book["author"]}")

print("Select a title to download")
selections_input = input("0,1,2-6 : ")

title_selections = parse_input(selections_input, books)



# For each selected book, get the data
for title_index in title_selections:
    # Create tmp directory with absolute path
    tmp_dir = os.path.abspath(os.path.join(os.getcwd(), "tmp"))
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir, mode=0o755)

    # Get book selection from index
    book_selection = get_book_by_index(title_index, books)

    print(f"Accessing {book_selection["title"]}, ID: {book_selection["id"]}")


    # Use scraper.py to download book info, scraper now downloads all the files to tmp_dir itself
    book_data = scraper.getBook(book_selection["link"], tmp_dir) # (chapter_markers, expected_time)

    if book_data:
        # Reformat returned tuple for easier readability
        book_title = book_selection["title"]
        book_author = book_selection["author"]
        book_chapter_markers = book_data[0]
        book_expected_length = book_data[1]

        # Save current cookies for upcoming downloads
        cookies = scraper.getCookies()

        # Filter to remove punctuation from book title/author for file path
        filter_table = str.maketrans(dict.fromkeys(string.punctuation))
        download_path = os.path.abspath(os.path.join(scraper_config["download-dir"], 
                                            book_author.translate(filter_table), 
                                            book_title.translate(filter_table)))

        os.makedirs(download_path, exist_ok=True)


        if config.get("download_thunder_metadata", 0) or config.get("convert_audiobookshelf_metadata", 0):
            # Both of these require thunder metadata.
            metadata_path = os.path.abspath(os.path.join(download_path, 'info.json'))
            chapters_path = os.path.abspath(os.path.join(download_path, 'chapters.json'))
            with open(chapters_path, 'w') as f:
                json.dump(book_chapter_markers, f)
            if overdrive_download.downloadThunderMetadata(book_selection["id"], metadata_path):
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
            if file_conversions.encodeAACMultiprocessing(tmp_dir, tmp_dir, config.get("low_quality_encode", 0), config.get("encoder_count", 4)):
                print("Converted all files to AAC M4B")

            if file_conversions.concatM4B(tmp_dir, tmp_dir, 'temp.m4b'):
                print("Converted to single M4B")

            print("Generating metadata")
            ffmetadata.writeMetaFile(tmp_dir, book_chapter_markers, book_title, book_author, book_expected_length)
            
            print("Adding metadata to audiobook")
            cover_path = os.path.abspath(os.path.join(tmp_dir, "cover.jpg"))

            output_file = os.path.abspath(os.path.join(download_path, book_title.replace(" ", "")+".m4b"))
            if file_conversions.encodeMetadata(tmp_dir, "temp.m4b", output_file, "ffmetadata", cover_path):
                print("Finished file created")
                # Clean up temporary files
                try:
                    shutil.rmtree(tmp_dir)
                    print("Temporary files cleaned up")
                except Exception as e:
                    print(f"Warning: Could not remove temporary directory: {e}")

del scraper
