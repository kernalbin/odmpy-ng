import string
import os

def time_as_int(timestamp: str) -> int:
    """
    Converts a timestamp in 'HH:MM:SS' or 'MM:SS' format to an integer in milliseconds (1/1000s).
    
    Args:
        timestamp (str): A time string (e.g., '00:03:25' or '12:34')
        
    Returns:
        int: Time in milliseconds.
    """
    parts = timestamp.split(":")
    if len(parts) == 2:
        return (int(parts[0])*60 + int(parts[1]))*1000
    if len(parts) == 3:
        return (int(parts[0])*3600 + int(parts[1])*60 + int(parts[2]))*1000
    else:
        raise ValueError("Timestamp must be in 'MM:SS' or 'HH:MM:SS' format")

def write_metafile(tmp_dir, chaptertimes: list, title: str, author: str):
    """
    Generates an ffmpeg metadata file with chapter information.
    
    Args:
        tmp_dir (str): Directory where ffmetadata will be saved.
        chapter_times (list): list of ("chapter title", "h:m:s start", "h:m:s end").
        title (str): The book or album title.
        author (str): The book or album author.
    """
    filename = os.path.join(tmp_dir, "ffmetadata")
    punctuation_remover = str.maketrans(dict.fromkeys(string.punctuation))

    with open(filename, 'w') as f:
        # Metadata header
        f.write(";FFMETADATA1\n")
        f.write(f"album={title}\n")
        f.write(f"title={title}\n")
        f.write(f"artist={author}\n")
        f.write(f"album_artist={author}\n")

        # Write chapter data
        for chaptertime in chaptertimes:
            chapter_title, chapter_start, chapter_end = chaptertime
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={time_as_int(chapter_start)}\n")
            f.write(f"END={time_as_int(chapter_end)}\n")

            # Remove punctuation from chapter title
            clean_title = chapter_title.translate(punctuation_remover) if chapter_title else ''
            f.write(f"title={clean_title}\n")

