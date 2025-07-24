# odmpy-ng
**OverDrive Manager Next Generation** — a tool for downloading and organizing audiobooks from OverDrive.
⚠️ **Use at your own risk. Requires a valid library account.**

---

## Features

- Interactive or Docker-based audiobook downloader for OverDrive
- Scrapes audio URLs, chapters, and cover images
- Converts MP3s into .m4b files with embedded chapter metadata
- Generates metadata.json compatible with Audiobookshelf
- Customizable and automated scraping via Selenium
- Fully command-line compatible (one book per call)

---

## Running

Before running, you must configure the tool with a configuration file, see
Configuration section below.

### Option 1: Run with Docker

This (or docker compose) is the preferred usage method.

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
  -v .:/app:ro \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  odmpy-ng
```

---

### Option 2: Run with Docker Compose

This can make development easier, since it builds quicker and only needs to be
told the path to the books ouptut directory (and that can be provided by an
environment variable, AUDIOBOOK_FOLDER).

Use `./build-compose.py` to build the docker-compose file.

See `build-compose.py run --help` for odmpy-ng options.

Requirements:
- Docker Compose
- Git

```bash
git clone https://github.com/kernalbin/odmpy-ng.git
cd odmpy-ng
./build-compose.py -d ~/audiobooks run
```

---

### Option 3: Run Locally

Requirements:
- Python 3.9+
- Google Chrome
- [ffmpeg](https://ffmpeg.org/download.html)
- `pip install -r requirements.txt`

```bash
git clone https://github.com/kernalbin/odmpy-ng.git
cd odmpy-ng
python interactive.py [config_file_path]
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

Optionally, each library may have a '"site-id": int' key, which may be passed
to the -s option to skip past the library selection screen. Any site-id values
provided must be unique within your configuration file.

---

## Command Line Options

A quick look at the command line options:

```bash
$ ./build-compose.py -d ~/audiobooks run --help
Using image: selenium/standalone-chrome@sha256:27edde51c30256aa3dfab3c95141ce74fd971c58763f4f8c70ff7521faae3d2b.
@sha256:27edde51c30256aa3dfab3c95141ce74fd971c58763f4f8c70ff7521faae3d2b
Run commands as in-container user ubuntu (UID: 1000, GID: 1000)
Process arguments for /entrypoint.sh --help
Starting ODMPY-NG
usage: interactive.py [-h] [--id ID] [--retry] [--name-dir NAME_DIR] [--library LIBRARY | --site-id SITE_ID] config_file

positional arguments:
  config_file           Path to config file

options:
  -h, --help            show this help message and exit
  --id ID, -i ID        Libby ID for a single book to download
  --retry, -r           Allow retry of stopped downloads (if left in tmp dir)
  --name-dir NAME_DIR, -n NAME_DIR
                        Fixed subdirectory relative to /downloads to move single downloaded book to
  --library LIBRARY, -L LIBRARY
                        Index of library within config to download from
  --site-id SITE_ID, -s SITE_ID
                        Site-Id assigned in config to library to download from
```

This demo shows a run of the builder, which has two options you need to know
about: `-d`/`--download-base` and `run`. The first is the location of the
output directory for the downloaded files, and the second means after building,
run the audiobook downloader. Any options following `run` will be passed to the
downloader (note: they're all optional!). For freqent use, `-d` can be omitted
if AUDIOBOOK_FOLDER is set in your environment, leaving a very simple `run`
command.

Once you've used the downloader a few times and checked that it puts files in
the right places, you might want to check out the options. You can see the help
for them above, but here's a table with some brief descriptions:

| Option                | Description |
|-----------------------|-------------|
| `-i`, `--id`              | Libby ID for a single book to download. You can see this from your library's webpage for the book. |
| `-r`, `--retry`           | Allow retry of stopped downloads (if left in tmp dir). You can enable this after a download fails, the cleanup happens before the run, not after. |
| `-L`, `--library`         | If you have multiple libraries in your config, you can specify which one to download from, counted from 0. |
| `-s`, `--site-id`         | Same as above, but if your library entries have a site-id you can use that for this option. |
| `-n`, `--name-dir`        | This can only be used when you select one single book, either by --id or manually; it will place the downloaded book into the indicated subfolder of your -d downloads directory. |

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
- [ ] Batch download multiple books  
- [ ] Filter loans by media type
- [ ] Support for branch libraries

---

## ⚠️ Disclaimer

This tool is intended for personal use only.  
You must have a valid library account with OverDrive access.

> Use responsibly. The maintainers are not responsible for any misuse or violation of OverDrive’s terms of service.
