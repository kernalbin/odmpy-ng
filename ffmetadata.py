import string, os

# Converts 0:00:00 format strings to 1/1000s base integers.
def timeAsInt(text: str) -> int:
    splittext = text.split(":")
    if len(splittext) == 2:
        return (int(splittext[0])*60 + int(splittext[1]))*1000
    if len(splittext) == 3:
        return (int(splittext[0])*3600 + int(splittext[1])*60 + int(splittext[2]))*1000

# {'Intro': '00:00', 'For Tyler': '00:13'}

# Chaptertimes dictionary like example above
# Title of book
# Author of book
# Length of book (for last chapter end time)
# Writes to 'ffmetadata'
def writeMetaFile(tmp_dir, chaptertimes: dict, title: str, author: str, length: int):
    chapter_titles = list(chaptertimes.keys())
    table = str.maketrans(dict.fromkeys(string.punctuation))

    filename = os.path.join(tmp_dir, "ffmetadata")

    with open(filename, 'w') as f:

        f.write(";FFMETADATA1\n")
        f.write(f"album={title}\n")
        f.write(f"title={title}\n")
        f.write(f"artist={author}\n")
        f.write(f"album_artist={author}\n")

        for i, chapter_title in enumerate(chapter_titles):
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={timeAsInt(chaptertimes[chapter_title])}\n")

            if i+1 < len(chapter_titles):
                f.write(f"END={timeAsInt(chaptertimes[chapter_titles[i+1]])}\n")
            else:
                f.write(f"END={timeAsInt(length)-1}\n")

            f.write(f"title={chapter_title.translate(table)}\n")

# writeMetaFile(chapter_times_example, "Educated", "Unkown", "12:10:22")