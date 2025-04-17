import string, os

# Converts 0:00:00 format strings to 1/1000s base integers.
def timeAsInt(text: str) -> int:
    splittext = text.split(":")
    if len(splittext) == 2:
        return (int(splittext[0])*60 + int(splittext[1]))*1000
    if len(splittext) == 3:
        return (int(splittext[0])*3600 + int(splittext[1])*60 + int(splittext[2]))*1000

chapter_times_example = {'Intro': '00:00', 'For Tyler': '00:13', "Author's Note": '00:52', 'Prologue': '01:39', 'Part 1 - Chapter 1': '06:48', '"Grandma was a..."': '14:55', '"Fighting it out..."': '23:19', 'Chapter 2': '29:13', '"The woman returned several times..."': '38:11', '"The voices..."': '46:28', 'Chapter 3': '54:18', '"Mother used to tell..."': '1:02:58', 'Chapter 4': '1:11:25', '"It was a scorching..."': '1:18:45', '"I looked around..."': '1:25:26', 'Chapter 5': '1:33:31', '"Music became our..."': '1:42:17', '"I didn\'t believe..."': '1:51:11', '"Tyler rarely came home..."': '1:59:45', 'Chapter 6': '2:05:30', '"I wasn\'t the only..."': '2:12:32', '"The memory of Tyler..."': '2:21:36', '"By the time..."': '2:27:20', '"My back struck iron..."': '2:32:34', 'Chapter 7': '2:36:40', '"It didn\'t take long..."': '2:45:15', '"For 18 years..."': '2:51:22', 'Chapter 8': '2:56:51', '"Mother hadn\'t told Dad..."': '3:05:02', '"Mother must have..."': '3:09:13', 'Chapter 9': '3:14:49', '"The play opened..."': '3:21:46', '"Christmas was sparse..."': '3:28:42', 'Chapter 10': '3:33:15', '"A few days after..."': '3:40:17', 'Chapter 11': '3:45:50', '"It was a hazy.."': '3:53:34', 'Chapter 12': '3:59:55', '"The Worm Creek..."': '4:06:24', '"He was right..."': '4:11:30', 'Chapter 13': '4:16:53', '"I awoke with needles..."': '4:25:27', '"That night..."': '4:31:40', 'Chapter 14': '4:38:56', '"When I told Dad..."': '4:46:59', '"I struggled to..."': '4:55:34', 'Chapter 15': '5:01:57', '"Without Sean as..."': '5:06:55', '"Sean returned to work..."': '5:15:46', '"They shouted at each..."': '5:21:39', 'Chapter 16': '5:25:37', '"We folded Sean..."': '5:34:21', '"The envelope arrived..."': '5:39:35', 'Part 2 - Chapter 17': '5:45:36', '"The next morning..."': '5:50:07', '"I don\'t know..."': '5:56:20', 'Chapter 18': '6:01:28', '"One winter..."': '6:09:42', 'Chapter 19': '6:17:21', '"My memories of..."': '6:23:30', '"Charles and I..."': '6:27:51', 'Chapter 20': '6:32:45', '"The summer Sean and..."': '6:40:01', '"Our nigger\'s back..."': '6:45:56', 'Chapter 21': '6:49:20', '"Robin explained this..."': '6:54:10', 'Chapter 22': '6:58:32', '"Winter covered campus..."': '7:06:05', '"The shop in Franklin..."': '7:13:31', '"That night with..."': '7:19:27', 'Chapter 23': '7:24:56', '"I was shocked out..."': '7:32:00', '"I believed that.."': '7:39:17', 'Chapter 24': '7:44:46', '"I became obsessed..."': '7:52:41', '"I began to feel.."': '7:58:14', 'Chapter 25': '8:03:48', '"In this account..."': '8:12:10', 'Chapter 26': '8:20:11', '"I return to BYU..."': '8:25:52', 'Chapter 27': '8:30:03', '"The story of..."': '8:38:39', 'Chapter 28': '8:44:22', '"I wanted the mind..."': '8:50:33', '"At my next..."': '8:58:55', 'Chapter 29': '9:05:34', '"I was put..."': '9:12:43', '"A month before..."': '9:19:54', 'Part 3 - Chapter 30': '9:24:36', '"I attended a..."': '9:31:43', '"In December..."': '9:35:59', '"Mothe was overwhelmed..."': '9:40:02', 'Chapter 31': '9:47:14', '"For the rest of..."': '9:56:05', '"Because you were so..."': '10:02:50', 'Chapter 32': '10:08:11', '"My father lost his..."': '10:13:55', 'Chapter 33': '10:19:08', '"Buck\'s Peak was..."': '10:24:15', 'Chapter 34': '10:30:11', '"The blood on my..."': '10:39:07', 'Chapter 35': '10:44:28', '"After I read..."': '10:53:34', 'Chapter 36': '10:59:12', '"When I reflect..."': '11:07:45', '"I am called of..."': '11:16:24', 'Chapter 37': '11:19:55', '"I remember the drama..."': '11:27:50', '"My fellowship at..."': '11:33:30', 'Chapter 38': '11:37:22', '"Winter was long that..."': '11:45:03', 'Chapter 39': '11:49:51', '"Grandma over in town..."': '11:58:41', 'Chapter 40': '12:05:00', 'Credits': '12:09:44'}

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