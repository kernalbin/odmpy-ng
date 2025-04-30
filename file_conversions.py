import subprocess, os

def concatMP3(tmp_dir, download_path, out_file):
    partlist_file = os.path.join(tmp_dir, 'partlist.txt')
    out_file = os.path.join(tmp_dir, out_file)

    with open(partlist_file, 'w') as f: 
        for file in os.listdir(download_path):
            if file.endswith('.mp3'):
                # Use absolute paths in the partlist file
                abs_path = os.path.abspath(os.path.join(download_path, file))
                f.write(f"file '{abs_path}'\n")

    try:
        # Use argument list instead of string command
        result = subprocess.run([
            'ffmpeg', 
            '-y', 
            '-f', 'concat', 
            '-safe', '0', 
            '-i', partlist_file, 
            '-c', 'copy', 
            out_file
        ], check=False)
        
        return result.returncode == 0 or result.returncode == 1
    except Exception as e:
        print(f"Error concatenating MP3 files: {e}")
        return False
    
def encodeAAC(tmp_dir, in_file, out_file, lq=0):
    # Check if lq is True and set the bitrate accordingly
    if lq==1:
        bitrate = '32k'
    else:
        bitrate = '64k'  # Default to 64k for better quality
    in_file = os.path.join(tmp_dir, in_file)
    out_file = os.path.join(tmp_dir, out_file)

    try:
        # Use argument list instead of string command with improved quality settings
        result = subprocess.run([
            'ffmpeg', 
            '-y', 
            '-i', in_file, 
            '-c:a', 'aac', 
            '-b:a', bitrate,  # Set bitrate based on lq
            '-ar', '44100', # Maintain 44.1kHz sample rate
            '-ac', '2',     # Ensure stereo output (2 channels)
            '-profile:a', 'aac_low', # Use AAC-LC profile for compatibility
            out_file
        ], check=False)
        
        return result.returncode == 0 or result.returncode == 1
    except Exception as e:
        print(f"Error encoding AAC: {e}")
        return False

def encodeMetadata(tmp_dir, in_file, out_file, chapter_file, cover_file):
    in_file = os.path.join(tmp_dir, in_file)
    chapter_file = os.path.join(tmp_dir, chapter_file)
    # Ensure cover_file is properly handled (it might be an absolute path already)
    if not os.path.isabs(cover_file):
        cover_file = os.path.join(tmp_dir, cover_file)

    try:
        # Use argument list instead of string command
        result = subprocess.run([
            'ffmpeg', 
            '-y', 
            '-i', in_file, 
            '-i', cover_file, 
            '-i', chapter_file, 
            '-map', '0', 
            '-map', '1', 
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
