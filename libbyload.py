#!/bin/python3

import sys, os, time
import json
import argparse
import subprocess
from io import StringIO


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

def making_progress(base: Path, book: Book, verbose: bool = False, only_check_previous_run: bool = False) -> bool:
    progress = False
    path = base / 'tmp' / str(book.ID)
    if not path.is_dir():
        return True
    older_files = []
    older = path/'older.files'
    if older.is_file():
        with older.open('r') as f:
            older_files = f.read().splitlines()
    if only_check_previous_run:
        return len(older_files) > 0
    header = False
    for f in os.listdir(base / 'tmp' / str(book.ID)):
        if not f.endswith('.mp3') or f in older_files:
            continue
        if verbose:
            if not header:
                header = True
                print(f"Checking {book.title} for progress:")
            print(f"  {f}")
        older_files.append(f)
        progress = True
    if older_files:
        with older.open('w') as f:
            f.write('\n'.join(older_files))
    return progress

def build_docker(download_base: Path) -> dict[str, str]:
    # Set up environment for docker run.
    UID = os.getuid()
    GID = os.getgid()

    env = os.environ.copy()
    env["HOST_UID"] = str(UID)
    env["HOST_GID"] = str(GID)
    env["DOWNLOAD_BASE"] = str(download_base)
    env["COMPOSE_BAKE"] = "true"
    base_image = "selenium/standalone-chrome"

    # Use a pinned base image, update the pin once a day.
    needs_build = False
    full_image = base_image
    image_pin = Path('.') / 'image.pin'
    if image_pin.is_file():
        with image_pin.open('r') as f:
            full_image = f.read().strip()
    # If there's no pinned image or it's older than a day, pull the latest.
    if full_image == base_image or not '@' in full_image or time.time() - image_pin.stat().st_mtime > 24*60*60:
        print("Pulling base image...")
        res = subprocess.call(f'docker pull {base_image}', shell=True)
        if res != 0:
            print(f"Error pulling {base_image}: {res}")
            sys.exit(1)
        # Having pulled the latest image (which may not be changed!), record the digest.
        digest = subprocess.check_output(
            [ "docker", "inspect", "--format={{index .RepoDigests 0}}", base_image ],
            text=True).strip()
        if not '@' in digest:
            print(f"Error parsing digest for {base_image}: {digest}")
            sys.exit(1)
        if digest != full_image:
            needs_build = True
            full_image = digest
        # Update the pinning file, so timestamp shows.
        with image_pin.open('w') as f:
            f.write(digest)

    # Extract the "pin", which is the @sha256 part of the digest.
    env["SELENIUM_SHA"] = '@' + full_image.split('@')[1]

    print(f"Using image: {full_image}.")
    if needs_build:
        print("Building odmpy-ng image...")
        res = subprocess.call('docker compose build odmpy-ng', shell=True, env=env)
        if res != 0:
            print(f"Error building odmpy-ng: {res}")
            sys.exit(1)

    return env

def main():
    global libby_loc
    
    default_dest = os.getenv('AUDIOBOOK_FOLDER', None)

    # options
    args = argparse.ArgumentParser()
    args.add_argument('--build-only', action='store_true', help='Run docker compose build for odmpy-ng, do nothing else.')
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

    env = build_docker(download_base)
    if opts.build_only:
        sys.exit(0)

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

    for book in unrecorded:
        tmp_folder = download_base / 'tmp' / book.ID
        bad_marker = tmp_folder / 'bad'
        if bad_marker.is_file():
            print(f"Skipping book due to 'bad' flag (delete to retry): {book.title}: {bad_marker}")
            continue

        print(f"\nRunning odmpy-ng for book: {book.title}")

        was_previously_run = making_progress(download_base, book, only_check_previous_run=True)
        res = -1
        # Using try/finally to handle things like ctrl-c. Include a timeout.
        out_buf = StringIO()
        err_buf = StringIO()
        start_time = time.time()
        proc = None

        try:
            # Stream output live and collect it
            proc = subprocess.Popen(f"docker compose run --rm odmpy-ng -s={book.site_id} -i={book.ID} -n=libby/{book.ID} -r",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                                shell=True, text=True, env=env)
            if proc is None or proc.stdout is None or proc.stderr is None:
                print("Error downloading book {book.ID}, {book.title}: unable to start docker subprocess.")
                continue

            # Stream output in real time, so onlookers can see progress. Also
            # store in case of problems, or timeouts.
            for line in proc.stdout:
                out_buf.write(line)
                sys.stdout.write(line)
                sys.stdout.flush()
                # Handle timeout.
                elapsed = time.time() - start_time
                if elapsed > 60 * 30: # 30 minutes feels like enough!
                    stdout = proc.stdout.read() + '\n'
                    sys.stdout.write(stdout)
                    out_buf.write(stdout)
                    message = f"Timeout reached after {elapsed//60} minutes for book {book.ID}, killing process."
                    print(message)
                    out_buf.write(message + '\n')
                    if proc.poll() is None:
                        proc.kill()
                    break
        finally:
            # Collect stderr and cleanup proc.
            res = -1
            if proc is not None and proc.stdout is not None and proc.stderr is not None:
                stderr = proc.stderr.read() + '\n'
                sys.stdout.write(stderr)
                out_buf.write(stderr)
                proc.stderr.close()
                proc.stdout.close()
                res = proc.wait()
            else:
                print("Error downloading book {book.ID}, {book.title}: no subprocess started.")

            made_progress = making_progress(download_base, book, verbose=True)
            if res != 0 or not made_progress:
                print(f"Error running odmpy-ng for book {book.ID}, {book.title}: {res} ",
                      ("no progress made" if not made_progress else ""))
                # Given an error, dump the log so we might see why.
                if not os.path.exists(tmp_folder):
                    tmp_folder.mkdir(parents=True)
                log = tmp_folder / 'process.log'
                with log.open('a') as f:
                    f.write(out_buf.getvalue() + '\n==================\n')
                # Allow two attempts to make progress, then give up.
                if was_previously_run and not made_progress:
                    badfile = tmp_folder / 'bad'
                    print("Marking tmp folder as bad, previous downloads made but no progress this time:", badfile)
                    badfile.touch()

if __name__ == '__main__':
    main()

