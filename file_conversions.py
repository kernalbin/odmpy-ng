import subprocess, os, shutil

def concatMP3(tmp_dir, download_path, out_file):
    partlist_file = os.path.join(tmp_dir, 'partlist.txt')
    out_file = os.path.join(tmp_dir, out_file)


    with open(partlist_file, 'w') as f: 
        for file in os.listdir(download_path):
            if file.endswith('.mp3'):
                f.write(f"file '{file}'\n")

    exit_code = subprocess.call(f"ffmpeg -y -f concat -safe 0 -i \"{partlist_file}\" -c copy \"{out_file}\"")
    if exit_code == 0 or exit_code == 1:
        return True
    else:
        return False
    
def encodeAAC(tmp_dir, in_file, out_file):
    in_file = os.path.join(tmp_dir, in_file)
    out_file = os.path.join(tmp_dir, out_file)

    exit_code = subprocess.call(f"ffmpeg -y -i \"{in_file}\" -c:a aac -b:a 32k \"{out_file}\"") # 32k or 64k

    if exit_code == 0 or exit_code == 1:
        return True
    else: 
        return False

def encodeMetadata(tmp_dir, in_file, out_file, chapter_file, cover_file):
    in_file = os.path.join(tmp_dir, in_file)
    chapter_file = os.path.join(tmp_dir, chapter_file)

    exit_code = subprocess.call(f"ffmpeg -y -i \"{in_file}\" -i \"{cover_file}\" -i \"{chapter_file}\" -map 0 -map 1 -map_metadata 2 -map_chapters 2 -c copy -disposition:1 attached_pic \"{out_file}\"")

    if exit_code == 0 or exit_code == 1:
        return True
    else:
        return False