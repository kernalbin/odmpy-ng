import subprocess
import os
import multiprocessing
import re

def generate_partslist_m4b(tmp_dir, download_path):
    """
    Generate a FFmpeg-compatible part list for .m4b files in the download directory.

    Args:
        tmp_dir (str): Temporary directory to save the part list file.
        download_path (str): Directory containing .m4b files.

    Returns:
        str: Path to the generated partlist.txt file.
    """
    partlist_file = os.path.join(tmp_dir, 'partlist.txt')

    def extract_partnum(filename):
        match = re.search(r'(\d+)', filename)
        return int(match.group(1)) if match else -1

    # Collect and sort .m4b files based on part number
    sorted_files = sorted(
        [file for file in os.listdir(download_path) if file.endswith('.m4b')],
        key=extract_partnum
    )

    # Write each absolute path into the partslist file
    with open(partlist_file, 'w') as f: 
        for file in sorted_files:
            abs_path = os.path.abspath(os.path.join(download_path, file))
            f.write(f"file '{abs_path}'\n")

    return partlist_file

def get_mp3_files(download_path):
    """
    Retrieve a list of absolute paths to all .mp3 files in the download directory.

    Args:
        download_path (str): Directory containing .mp3 files.

    Returns:
        list: List of absolute paths to .mp3 files.
    """
    mp3files = []

    for file in os.listdir(download_path):
        if file.endswith('.mp3'):
            abs_path = os.path.abspath(os.path.join(download_path, file))
            mp3files.append(abs_path)

    return mp3files
    
def concat_m4b(tmp_dir, download_path, out_file):
    """
    Concatenate multiple .m4b files using FFmpeg.

    Args:
        tmp_dir (str): Temporary directory.
        download_path (str): Directory with .m4b parts.
        out_file (str): Output filename for the concatenated file.

    Returns:
        bool: True if FFmpeg executed successfully, False otherwise.
    """
    partlist_file = generate_partslist_m4b(tmp_dir, download_path)
    out_file = os.path.join(tmp_dir, out_file)

    try:
        result = subprocess.run([
            'ffmpeg', 
            '-y', 
            '-f', 'concat', 
            '-safe', '0', 
            '-i', partlist_file, 
            '-c', 'copy', out_file
        ], check=False)
        
        return result.returncode in [0, 1] # FFmpeg sometimes returns 1 for non-critical warnings
    except Exception as e:
        print(f"Error concatenating AAC files: {e}")
        return False
    
def encode_aac(args):
    """
    Convert an MP3 file to M4B using FFmpeg with optional low quality.

    Args:
        args (tuple): (tmp_dir, in_file_path, lq) where lq is 1 for low quality.

    Returns:
        bool: True if encoding succeeds, False otherwise.
    """
    tmp_dir, in_file, lq = args

    # Check if lq is 1 and set the bitrate accordingly
    if lq==1:
        bitrate = '32k'
    else:
        bitrate = '64k'

    in_file = os.path.join(tmp_dir, in_file)
    out_file = os.path.join(tmp_dir, in_file.replace('.mp3', '.m4b'))

    print(f"Converting: {in_file} -> {out_file}")

    try:
        result = subprocess.run([
            'ffmpeg', 
            '-y', 
            '-i', in_file, 
            '-c:a', 'aac', 
            '-b:a', bitrate,  # Set bitrate based on lq
            '-ar', '44100', # Maintain 44.1kHz sample rate
            '-ac', '2',     # Ensure stereo output (2 channels) - is this necessary?
            '-profile:a', 'aac_low', # Use AAC-LC profile for compatibility
            out_file
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        print(f"Finished: {in_file} -> {out_file}")

        return result.returncode == 0 or result.returncode == 1
    except Exception as e:
        print(f"Error encoding AAC: {e}")
        return False
    
def encode_aac_multiprocessing(tmp_dir, download_path, lq=0, num_processes=4):
    """
    Encode all MP3 files in parallel to M4B format.

    Args:
        tmp_dir (str): Temporary directory.
        download_path (str): Directory with .mp3 files.
        lq (int): 1 for low quality, 0 for standard.
        num_processes (int): Number of worker processes.

    Returns:
        bool: True if all files were encoded.
    """
    mp3Files = get_mp3_files(download_path)
    print(f"{len(mp3Files)} MP3 file(s) found")

    args = [(tmp_dir, mp3, lq) for mp3 in mp3Files]

    with multiprocessing.Pool(processes=min(num_processes, len(mp3Files))) as pool:
        pool.map(encode_aac, args)

    print("All files encoded")
    return True


def encode_metadata(tmp_dir, in_file, out_file, chapter_file, cover_file):
    """
    Attach metadata, chapter markers, and cover image to the final M4B file using FFmpeg.

    Args:
        tmp_dir (str): Temporary directory.
        in_file (str): Input M4B filename.
        out_file (str): Output M4B filename with metadata.
        chapter_file (str): Metadata file with chapter info.
        cover_file (str): Path to the cover image file.

    Returns:
        bool: True if metadata attachment succeeds, False otherwise.
    """
    in_file = os.path.join(tmp_dir, in_file)
    chapter_file = os.path.join(tmp_dir, chapter_file)
    # Ensure cover_file is properly handled (it might be an absolute path already)
    if not os.path.isabs(cover_file):
        cover_file = os.path.join(tmp_dir, cover_file)

    try:
        result = subprocess.run([
            'ffmpeg', 
            '-y', 
            '-i', in_file, 
            '-i', cover_file, 
            '-i', chapter_file, 
            '-map', '0', '-map', '1', 
            '-map_metadata', '2', 
            '-map_chapters', '2', 
            '-c', 'copy', 
            '-disposition:1', 'attached_pic', 
            out_file
        ], check=False)
        
        return result.returncode == 0 or result.returncode == 1
    except Exception as e:
        print(f"Error encoding metadata: {e}")
        return False
