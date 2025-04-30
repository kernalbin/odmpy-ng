# odmpy-ng
Over Drive Manager NG

More info to come...

Started working on this when I learned omdpy was basically dead. I want a good way to headlessly and non-interactively download audiobooks from libby/overdrive. And while it does take a while, this doees have the potential to do just that.

## Usage

Running interactive.py on a machine with a screen and chrome installed is possible, you'll also need to install requirements.txt and ffmpeg. Likely you'll want to modify where it downloads to as well.

There is also a Dockerfile, which may be easier, git clone then build and run it. 
```
git clone https://github.com/kernalbin/odmpy-ng.git
cd odmpy-ng
docker build -t odmpy-ng .
docker run -it --rm -v ./config:/config -v ./downloads:/downloads odmpy-ng
```

In either case you need to fill out a config file. 

## interactive.py
This is the the main script that coordinates the display and collection of audiobooks.

## scraper.py
This is what scrapes book data from overdrive, including audio urls, cover and chapter info.
Its semi reliable, but quite slow, especially in books with many chapters.

## overdrive_download.py
This uses the scraper info and cookies to download the audiobook in its parts.
Simple python requests script.

## ffmetadata.py
Converts the chapter information, along with Title/Author to a metadata file to embed into the m4b file.

## file_conversions.py
Converts the mp3s and other info into a m4b file with half decent metadata.
AAC Encodes can take a while, but afaik are required to use .m4b container? Which I heavily prefer.

## to-do
To minimize chance of identification as "bot" behavior. See http requests/responses with DevTools, there is an analytics ping request made after listening to each part

Fully command line compatible / non-interactive

Download multiple books in one command

Long chapters can cause missing mp3 parts.

## Disclaimer
To use odmpy-ng, you must have a valid library account. Use at your own risk.