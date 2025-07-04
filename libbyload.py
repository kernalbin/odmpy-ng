#!/bin/python3

import sys, os
import json
import argparse
import subprocess
import shutil

from pathlib import Path
from dataclasses import dataclass

libby_loc = '/tmp/libby.json'

@dataclass
class Book:
    ID: int
    title: str
    site_id: int

def load_libby():
    # Run odmpy to get the data, check the return code
    res = subprocess.call('odmpy libby --exportloans ' + libby_loc, shell=True)
    if res != 0:
        print(f"Error running odmpy libby: {res}")
        sys.exit(1)
    with open(libby_loc, 'r') as f:
        data = json.load(f)
    return data

def main():
    global libby_loc
    
    default_dest = os.getenv('AUDIOBOOK_FOLDER', None)

    # options
    args = argparse.ArgumentParser()
    args.add_argument('-l', '--libby', help='full name for libby json file', default=libby_loc)
    args.add_argument(
        '-d', '--dest',
        type=str,
        default=default_dest,
        help=f'Directory under which files will be finally stored (default: AUDIOBOOK_FOLDER environment variable={default_dest})'
    )

    # parse
    opts = args.parse_args()
    libby_loc = opts.libby

    if not libby_loc or not Path(libby_loc).is_file():
        print(f"Error: {libby_loc} is not a file")
        sys.exit(1)

    if not opts.dest:
        print("Error: no destination directory specified")
        sys.exit(1)

    download_base = Path(opts.dest)

    libby_dest = download_base / 'libby'
    if not libby_dest.is_dir():
        print(f"Warning: libby path {libby_dest} is not a directory, attempting to create")
        libby_dest.mkdir(parents=True)

    data = load_libby()
    unrecorded = []
    print(f"Scanning for needed books in {libby_dest}:")
    for item in data:
        ID = item['id']
        title = item['title']
        site_id = item['websiteId']

        if not Path(libby_dest / ID).is_dir():
            print(f"  {ID} - {title} ({site_id})")
            unrecorded.append(Book(ID, title, site_id))

    if not unrecorded:
        print("Nothing to do, exiting.")
        sys.exit(0)

    UID = os.getuid()
    GID = os.getgid()

    for book in unrecorded:
        print(f"Running odmpy-ng for book '{book.title}'")
        res = subprocess.call(f"docker run --rm -e HOST_UID={UID} -e HOST_GID={GID} "
                             f"-v ./config:/config -v {download_base}:/downloads -v {os.getcwd()}:/app:ro "
                             f"odmpy-ng -s={book.site_id} -i={book.ID} -n=libby/{book.ID}",
                             shell=True)
        if res != 0:
            print(f"Error running odmpy libby for book {book.ID} / {book.title}: {res}")
            sys.exit(1)

if __name__ == '__main__':
    main()

