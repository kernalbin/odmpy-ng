import json, subprocess, os, string, shutil
import ffmetadata
from scraper import Scraper
import overdrive_download
import file_conversions

print("Starting ODMPY-NG")

cookies = []

with open("config") as f:
    config = json.load(f)
if os.path.exists("cookies"):
    with open("cookies") as f:
        cookies = json.load(f)

print("Config loaded:")
print(config)

if cookies:
    print("Cookies loaded:")
    print(cookies)

scraper = Scraper(config)

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

    tmp_dir = ".\\tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    cookies = scraper.getCookies()
    del scraper

    filter_table = str.maketrans(dict.fromkeys(string.punctuation))
    download_path = os.path.join(config["download-dir"], book_author.translate(filter_table), book_title.translate(filter_table))

    if not os.path.exists(download_path):
        os.makedirs(download_path)

    cover_dir = os.path.join(tmp_dir, "cover.jpg")
    
    if overdrive_download.downloadCover(book_cover_image_url, cover_dir, cookies):
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
    output_file = os.path.join(download_path, book_title.replace(" ", "")+".m4b")
    if file_conversions.encodeMetadata(tmp_dir, "temp.m4b", output_file, "ffmetadata", cover_dir):
        print("Finished file created")
        shutil.rmtree(tmp_dir)