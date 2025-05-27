import requests
import os
import json
import convert_metadata

# Standard headers for web requests to mimic a browser
headers = {'User-Agent': 'Mozilla/5.0'}

def download_mp3_part(url, part_id, download_path: str, cookies: list) -> int:
    """
    Downloads an MP3 part from the given URL and saves it to the specified path.
    
    Args:
        url (str): The URL of the MP3 part.
        part_id (int): The part number, used to name the file.
        download_path (str): Directory where the MP3 will be saved.
        cookies (list): List of cookies (dicts) for authentication.
    
    Returns:
        int: Duration of the downloaded MP3 in seconds, or 0 on failure.
    """
    os.makedirs(download_path, exist_ok=True)
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    print("Downloading part " + str(int(part_id)))
    response = requests.get(url, headers=headers, cookies=cookie_dict, stream=True)

    if response.status_code == 200:
        with open(os.path.join(download_path, f"part{part_id}.mp3"), "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return convert_metadata.get_mp3_duration(os.path.join(download_path, f"part{part_id}.mp3"))
    else:
        print(f"Failed to download mp3 part with status code {response.status_code}")
        return 0


def download_cover(cover_url: str, download_path: str, cookies: list, abort=False):
    """
    Downloads a cover image from the given URL to the specified file path.
    
    Args:
        cover_url (str): URL of the cover image.
        download_path (str): File path to save the downloaded image.
        cookies (list): List of cookies (dicts) for authentication.
        abort (bool): If True, raise an exception on failure.
    
    Returns:
        bool: True if download succeeded, False otherwise.
    """

    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    response = requests.get(cover_url, headers=headers, cookies=cookie_dict, stream=True)
    
    if response.status_code == 200:
        with open(download_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return True
    else:
        print(f"Failed to download cover with status code {response.status_code}")
        if abort:
            response.raise_for_status()
        return False

def download_thunder_metadata(book_id: int, download_path: str) -> bool:
    """
    Downloads metadata for a book using the Thunder API and saves it to a file.
    
    Args:
        book_id (int): Unique book ID used by Thunder API.
        download_path (str): File path to save the metadata JSON.
    
    Returns:
        bool: True if download and write succeeded, False otherwise.
    """
    api_url = f"https://thunder.api.overdrive.com/v2/media/{book_id}"
    response = requests.get(api_url)

    if response.status_code == 200:
        book_metadata = response.json()
        with open(download_path, 'w') as f:
            json.dump(book_metadata, f, ensure_ascii=False, indent=4)
        return True
    else:
        print(f"Failed to download metadata with status code {response.status_code}")
        return False