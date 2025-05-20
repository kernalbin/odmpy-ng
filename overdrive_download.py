import requests, collections, os, json
import convert_metadata

headers = {'User-Agent': 'Mozilla/5.0'}


def downloadMP3(book_urls, download_path, cookies):
    ordered_urls = collections.OrderedDict(sorted(book_urls.items()))
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    for part_id, audio_file in ordered_urls.items():
        print("Downloading part " + str(int(part_id)))
        response = requests.get(audio_file, headers=headers, cookies=cookie_dict, stream=True)

        if response.status_code == 200:
            with open(os.path.join(download_path, f"part{part_id}.mp3"), "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        else:
            print(f"Download failed: {response.status_code}")
            return False
        
    return True

def downloadMP3Part(url, part_id, download_path, cookies) -> int: # Downloads mp3 part to download_path/part[ID].mp3 and returns the length in seconds
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    print("Downloading part " + str(int(part_id)))
    response = requests.get(url, headers=headers, cookies=cookie_dict, stream=True)

    if response.status_code == 200:
        with open(os.path.join(download_path, f"part{part_id}.mp3"), "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return convert_metadata.get_mp3_duration(os.path.join(download_path, f"part{part_id}.mp3"))
    else:
        print(f"Download failed: {response.status_code}")
        return 0


def downloadCover(cover_url, download_path, cookies):

    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    response = requests.get(cover_url, headers=headers, cookies=cookie_dict, stream=True)
    if response.status_code == 200:
        with open(download_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return True
    return False

def downloadThunderMetadata(book_id: int, download_path):
    api_url = f"https://thunder.api.overdrive.com/v2/media/{book_id}"

    response = requests.get(api_url)

    if response.status_code == 200:
        book_metadata = response.json()
        with open(download_path, 'w') as f:
            json.dump(book_metadata, f, ensure_ascii=False, indent=4)
        return True
    print(f"Failed to download metadata with status code {response.status_code}")
    return False