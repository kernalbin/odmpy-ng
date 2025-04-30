import requests, json, subprocess, collections, os, string

headers = {'User-Agent': 'Mozilla/5.0'}


def downloadMP3(book_urls, download_path, cookies):
    ordered_urls = collections.OrderedDict(sorted(book_urls.items()))
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    for part_id, audio_file in ordered_urls.items():
        print("Downloading part " + part_id)
        response = requests.get(audio_file, headers=headers, cookies=cookie_dict, stream=True)

        if response.status_code == 200:
            with open(os.path.join(download_path, f"part{part_id}.mp3"), "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        else:
            print(f"Download failed: {response.status_code}")
            return False
        
    return True


def downloadCover(cover_url, download_path, cookies):

    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    response = requests.get(cover_url, headers=headers, cookies=cookie_dict, stream=True)
    if response.status_code == 200:
        with open(download_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return True
    return False