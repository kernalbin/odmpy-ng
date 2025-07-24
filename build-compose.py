#!/bin/python3

import sys, os, time
import argparse
import subprocess

from pathlib import Path

def build_docker(download_base: Path, tmp_base: Path) -> dict[str, str]:
    # Set up environment for docker run.
    UID = os.getuid()
    GID = os.getgid()

    env = os.environ.copy()
    env["HOST_UID"] = str(UID)
    env["HOST_GID"] = str(GID)
    env["DOWNLOAD_BASE"] = str(download_base)
    env["TMP_BASE"] = str(tmp_base)
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
    image_pin = '@' + full_image.split('@')[1]
    env["SELENIUM_SHA"] = image_pin

    print(f"Using image: {full_image}.")
    if needs_build:
        print("Building odmpy-ng image...")
        res = subprocess.call('docker compose build odmpy-ng', shell=True, env=env)
        if res != 0:
            print(f"Error building odmpy-ng: {res}")
            sys.exit(1)

    print(image_pin)
    return env

def main():
    default_dest = os.getenv('AUDIOBOOK_FOLDER', None)
    default_tmp = os.getenv('TMP_BASE', None)
    if not default_tmp and default_dest:
        default_tmp = Path(default_dest) / 'tmp'

    # options
    args = argparse.ArgumentParser()
    args.add_argument(
        '-d', '--dest',
        type=str,
        default=default_dest,
        help=f'Directory under which files will be finally stored (default: AUDIOBOOK_FOLDER environment variable={default_dest})'
    )
    args.add_argument(
        '-t', '--tmp',
        type=str,
        default=default_tmp,
        help=f'Directory under which temporary files will be stored (default: TMP_BASE environment variable or dest/tmp)'
    )
    # Use argument 'run' to call the docker with the rest of the arguments.
    args.add_argument('run', nargs=argparse.REMAINDER)

    # parse
    opts = args.parse_args()

    if not opts.dest:
        print("Error: no destination directory specified, use -d or AUDIOBOOK_FOLDER environment variable")
        sys.exit(1)
    if not opts.tmp:
        print("Error: no temporary directory specified, use -t or TMP_BASE environment variable")
        sys.exit(1)

    env = build_docker(Path(opts.dest), Path(opts.tmp))

    if opts.run:
        res = subprocess.call("docker compose run -it --rm odmpy-ng " + ' '.join(opts.run[1:]), shell=True, env=env)
        sys.exit(res)

if __name__ == '__main__':
    main()

