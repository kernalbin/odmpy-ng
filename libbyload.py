#!/bin/python3

import sys, os
import json
import argparse
import subprocess
import shutil

from atomicwrites import atomic_write
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

def making_progress(base: Path, book: Book, verbose: bool = False) -> bool:
    progress = False
    path = base / 'tmp' / str(book.ID)
    if not path.is_dir():
        return True
    older_files = []
    older = path/'older.files'
    if older.is_file():
        with older.open('r') as f:
            for line in f:
                older_files.append(line.strip())
    if verbose:
        print(f"Checking {book.title} for progress:")
    for f in os.listdir(base / 'tmp' / str(book.ID)):
        if not f.endswith('.mp3') or f in older_files:
            continue
        if verbose:
            print(f"  {f}")
            older_files.append(f)
        progress = True
    with atomic_write(older, overwrite=True) as f:
        f.write('\n'.join(older_files))
    return progress

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

    env = os.environ.copy()
    env["HOST_UID"] = str(UID)
    env["HOST_GID"] = str(GID)
    env["DOWNLOAD_BASE"] = str(download_base)
    env["COMPOSE_BAKE"] = "true"

    res = subprocess.run(["docker", "compose", "build"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True,
                         env=env)
    # Check for failure
    if res.returncode != 0:
        print("Build failed. Dumping build output...\n", file=sys.stderr)
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)

    for book in unrecorded:
        tmp_folder = download_base / 'tmp' / book.ID
        if (tmp_folder / 'bad').is_file():
            print(f"Skipping book due to 'bad' flag (delete to retry): {book.title}: {tmp_folder / 'bad'}")
            continue
        print(f"Running odmpy-ng for book: {book.title}")
        res = -1
        try:
            # Using try/finally to handle things like ctrl-c.
            res = subprocess.call(f"docker compose run --rm odmpy-ng -s={book.site_id} -i={book.ID} -n=libby/{book.ID} -r",
                                shell=True, env=env)
            if not making_progress(download_base, book):
                res = -1
        finally:
            if res != 0:
                print(f"Error running odmpy libby for book {book.ID}, {book.title}: {res}")
                # Scan for leftover files in tmp folder...
                if os.path.exists(tmp_folder):
                    if not making_progress(download_base, book, verbose=True):
                        print("Marking tmp folder as bad, no progress.")
                        (tmp_folder / 'bad').touch()
                sys.exit(1)

if __name__ == '__main__':
    main()

