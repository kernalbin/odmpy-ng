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

def write_metafile(tmp_dir, chaptertimes: dict, title: str, author: str, length: str):
    """
    Generates an ffmpeg metadata file with chapter information.
    
    Args:
        tmp_dir (str): Directory where ffmetadata will be saved.
        chapter_times (dict): Dictionary mapping chapter titles to time strings.
                              Example: {'Intro': '00:00', 'Chapter 1': '00:13'}
        title (str): The book or album title.
        author (str): The book or album author.
        length (str): Total duration of the audio as H:M:S.
    """
    filename = os.path.join(tmp_dir, "ffmetadata")
    punctuation_remover = str.maketrans(dict.fromkeys(string.punctuation))
    chapter_titles = list(chaptertimes.keys())

    with open(filename, 'w') as f:
        # Metadata header
        f.write(";FFMETADATA1\n")
        f.write(f"album={title}\n")
        f.write(f"title={title}\n")
        f.write(f"artist={author}\n")
        f.write(f"album_artist={author}\n")

        # Write chapter data
        for i, chapter_title in enumerate(chapter_titles):
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={time_as_int(chaptertimes[chapter_title])}\n")

            # Determine end time of chapter
            if i+1 < len(chapter_titles):
                f.write(f"END={time_as_int(chaptertimes[chapter_titles[i+1]])}\n")
            else:
                # Use book length for last chapter
                # minus 1ms to prevent overlap
                f.write(f"END={time_as_int(length)-1}\n")

            # Remove punctuation from chapter title
            clean_title = chapter_title.translate(punctuation_remover)
            f.write(f"title={clean_title}\n")
