# odmpy-ng
**OverDrive Manager Next Generation** — a tool for downloading and organizing audiobooks from OverDrive.
⚠️ **Use at your own risk. Requires a valid library account.**

---

## Features

- Interactive or Docker-based audiobook downloader for OverDrive
- Scrapes audio URLs, chapters, and cover images
- Converts MP3s into .m4b files with embedded chapter metadata
- Customizable and automated scraping via Selenium

---

## Installation


### Option 1: Run with Docker

This is the preferred usage method.

Requirements:
- Docker
- Git

```bash
git clone https://github.com/kernalbin/odmpy-ng.git
cd odmpy-ng
docker build -t odmpy-ng .
docker run -it --rm \
  -v ./config:/config \
  -v ./downloads:/downloads \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  odmpy-ng
```

---

### Option 2: Run Locally

Requirements:
- Python 3.9+
- Google Chrome
- [ffmpeg](https://ffmpeg.org/download.html)
- `pip install -r requirements.txt`

```bash
git clone htttps://github.com/kernalbin/odmpy-ng.git
cd odmpy-ng
python interactive.py \[config_file_path\]
```

> **Note:** You may want to modify the default download path

---

## Configuration

You'll need to create a configuration file with your library's OverDrive URL and login credentials.  
Example `config.json`:

```json
{
    "libraries": [
        {
            "name": "Example Library",
            "url": "https://yourlibrary.overdrive.com",
            "card_number": "YOUR_CARD_NUMBER",
            "pin": "YOUR_PIN"
        }
    ],
    "low_quality_encode": 0,
    "download_thunder_metadata": 0,
    "convert_audiobookshelf_metadata": 0,
    "abort_on_warning": 0,
    "skip_reencode": 0,
    "encoder_count": 4
}
```

---

## Project Structure

| File / Script             | Description |
|--------------------------|-------------|
| `interactive.py`         | Main entry point — interactive selection and download UI |
| `scraper.py`             | Scrapes OverDrive for audio, chapter, and cover metadata |
| `overdrive_download.py`  | Downloads MP3 parts using scraped info and cookies |
| `ffmetadata.py`          | Creates chapter and metadata file for m4b embedding |
| `file_conversions.py`    | Converts MP3s into m4b with AAC and metadata |
| `Dockerfile`             | Docker setup using Selenium Chrome base image |
| `entrypoint.sh`          | Entrypoint script for Docker container |

---

## Roadmap

- [ ] Minimize bot-like behavior to reduce detection risk  
- [x] Fully command-line compatible (partial support)  
- [x] Batch download multiple books (testing)  
- [ ] Fix occasional missing MP3 parts on long chapters  
- [ ] Add loan renewal/return support  
- [ ] Filter loans by media type  
- [ ] Re-enable persistent cookies for session continuity  

---

## ⚠️ Disclaimer

This tool is intended for personal use only.  
You must have a valid library account with OverDrive access.

> Use responsibly. The maintainers are not responsible for any misuse or violation of OverDrive’s terms of service.