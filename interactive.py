<<<<<<< HEAD
import json, os, string, shutil, sys
=======
import json, os, string, shutil
>>>>>>> d73854ec6ee0b4df4e2847e4f3c5cb8621afe485
import ffmetadata
from scraper import Scraper
import overdrive_download
import file_conversions

print("Starting ODMPY-NG")

cookies = []

<<<<<<< HEAD
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

if os.path.exists("cookies"):
    try:
        with open("cookies") as f:
            cookies = json.load(f)
    except Exception as e:
        print(f"Error loading cookies: {e}")
        cookies = []

print("Config loaded")

# Handle multiple libraries
if "libraries" in config and len(config["libraries"]) > 0:
    print("\nAvailable libraries:")
    for i, library in enumerate(config["libraries"]):
        print(f"{i}: {library['name']} - {library['url']}")
    
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
        "download-dir": config["download-dir"]
    }
    
    print(f"Using library: {selected_library['name']}")
else:
    # Fall back to old format for backwards compatibility
    print("No libraries found in config file. Using legacy format.")
    scraper_config = config
=======
with open("config") as f: # {"library": "", "user": "", "pass": "", "download-dir": ""}
    config = json.load(f)
if os.path.exists("cookies"):
    with open("cookies") as f:
        cookies = json.load(f)

print("Config loaded:")
print(config)
>>>>>>> d73854ec6ee0b4df4e2847e4f3c5cb8621afe485

if cookies:
    print("Cookies loaded:")
    print(cookies)

<<<<<<< HEAD
scraper = Scraper(scraper_config)
=======
scraper = Scraper(config)
>>>>>>> d73854ec6ee0b4df4e2847e4f3c5cb8621afe485

cookies = scraper.ensureLogin(cookies)
with open("cookies", "w") as f:
    json.dump(cookies, f, indent=4)

books = scraper.getLoans()

for index, title, author, access_url in books:
    print(f"{index}: {title} - {author}")

title_index = int(input("Select a title to download: "))

book_data = scraper.getBook(books, title_index) # (urls, chapter_markers, cover_image_url, expected_time)

if book_data:
    print(f"Found {len(book_data[0])} parts")
    input("Enter to download")

    book_title = books[title_index][1]
    book_author = books[title_index][2]
    book_urls = book_data[0]
    book_chapter_markers = book_data[1]
    book_cover_image_url = book_data[2]
    book_expected_length = book_data[3]

<<<<<<< HEAD
    # Create tmp directory with absolute path
    tmp_dir = os.path.abspath(os.path.join(os.getcwd(), "tmp"))
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir, mode=0o755)
=======
    tmp_dir = ".\\tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
>>>>>>> d73854ec6ee0b4df4e2847e4f3c5cb8621afe485

    cookies = scraper.getCookies()
    del scraper

    filter_table = str.maketrans(dict.fromkeys(string.punctuation))
<<<<<<< HEAD
    download_path = os.path.abspath(os.path.join(scraper_config["download-dir"], 
                                          book_author.translate(filter_table), 
                                          book_title.translate(filter_table)))

    if not os.path.exists(download_path):
        os.makedirs(download_path, exist_ok=True)

    # Use absolute paths for all file operations
    cover_path = os.path.abspath(os.path.join(tmp_dir, "cover.jpg"))
    
    if overdrive_download.downloadCover(book_cover_image_url, cover_path, cookies):
=======
    download_path = os.path.join(config["download-dir"], book_author.translate(filter_table), book_title.translate(filter_table))

    if not os.path.exists(download_path):
        os.makedirs(download_path)

    cover_dir = os.path.join(tmp_dir, "cover.jpg")
    
    if overdrive_download.downloadCover(book_cover_image_url, cover_dir, cookies):
>>>>>>> d73854ec6ee0b4df4e2847e4f3c5cb8621afe485
        print("Downloaded Cover")

    if overdrive_download.downloadMP3(book_urls, tmp_dir, cookies):
        print("Downloaded Audio")

    if file_conversions.concatMP3(tmp_dir, tmp_dir, "temp.mp3"):
        print("Converted to single MP3")

    if file_conversions.encodeAAC(tmp_dir, "temp.mp3", "temp.m4b"):
        print("Converted to AAC M4B")

    print("Generating metadata")
    ffmetadata.writeMetaFile(tmp_dir, book_chapter_markers, book_title, book_author, book_expected_length)
    
    print("Adding metadata to audiobook")
<<<<<<< HEAD
    output_file = os.path.abspath(os.path.join(download_path, book_title.replace(" ", "")+".m4b"))
    if file_conversions.encodeMetadata(tmp_dir, "temp.m4b", output_file, "ffmetadata", cover_path):
        print("Finished file created")
        # Clean up temporary files
        try:
            shutil.rmtree(tmp_dir)
            print("Temporary files cleaned up")
        except Exception as e:
            print(f"Warning: Could not remove temporary directory: {e}")
=======
    output_file = os.path.join(download_path, book_title.replace(" ", "")+".m4b")
    if file_conversions.encodeMetadata(tmp_dir, "temp.m4b", output_file, "ffmetadata", cover_dir):
        print("Finished file created")
        shutil.rmtree(tmp_dir)
>>>>>>> d73854ec6ee0b4df4e2847e4f3c5cb8621afe485
