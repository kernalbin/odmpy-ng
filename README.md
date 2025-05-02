# odmpy-ng
Over Drive Manager NG. Use at your own risk.

## Usage

Running interactive.py on a machine with a screen and chrome installed is possible, you'll also need to install requirements.txt and ffmpeg. Likely you'll want to modify where it downloads to as well.

There is also a Dockerfile, which may be easier, git clone then build and run it. 
```
git clone https://github.com/kernalbin/odmpy-ng.git
cd odmpy-ng
docker build -t odmpy-ng .
docker run -it --rm -v ./config:/config -v ./downloads:/downloads -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) odmpy-ng
```

In either case you need to fill out a config file. 

### interactive.py
This is the the main script that coordinates the display and collection of audiobooks.

### scraper.py
This is what scrapes book data from overdrive, including audio urls, cover and chapter info.
Its semi reliable, but quite slow, especially in books with many chapters.

### overdrive_download.py
This uses the scraper info and cookies to download the audiobook in its parts.
Simple python requests script.

### ffmetadata.py
Converts the chapter information, along with Title/Author to a metadata file to embed into the m4b file.

### file_conversions.py
Converts the mp3s and other info into a m4b file with half decent metadata.
AAC Encodes can take a while, but afaik are required to use .m4b container? Which I heavily prefer.

## Roadmap
- [ ] Minimize chance of identification as "bot" behavior.
- [x] Fully command line compatible / non-interactive - Partial
- [x] Download multiple books in one command - Testing
- [ ] Long chapters can cause missing mp3 parts.
- [ ] Return / Renew loans
- [ ] Filter loans by media type
- [ ] Persistent cookies again

## Disclaimer
To use odmpy-ng, you must have a valid library account. Use at your own risk.
