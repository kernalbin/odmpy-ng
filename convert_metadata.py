#!/bin/python3.11
import os
import json, sys, string, itertools
from typing import List, Set
from mutagen.mp3 import MP3

# TODO - load canonical data... I shoouldn't have tried to autocorrect using
# Python's title() function, it's buggy in its original design and no longer
# fixable. I need to get tag names from data files (and fix by hand).
def normalize_tag(tag: str) -> str:
    #return canonical_tags.get((t := string.capwords(tag.strip())), t)
    t = tag.strip()
    if t.isupper():
        t = string.capwords(t)
    return canonical_tags.get(t, t)

def get_mp3_duration(filepath):
    """Returns the duration of an MP3 file in seconds."""
    mp3 = MP3(filepath)
    length = mp3.info.length
    if mp3.info.sketchy:
        raise ValueError(f"Corrupted MP3 file: {filepath}")
    return mp3.info.length

def get_total_duration(directory) -> int:
    """Calculates the total duration of all MP3 files in a directory."""
    total_duration = 0
    for filename in os.listdir(directory):
        if filename.endswith(".mp3"):
            filepath = os.path.join(directory, filename)
            total_duration += get_mp3_duration(filepath)
    return int(total_duration)

def abs_from_pylibby(container, mark_autoloaded=["Misordered"]):
    # pylibby uses two different formats, not sure why.
    if 'media_info' in container:
        input_data = container["media_info"]
        # The subtitle (if any) is in a different path.
        subtitle = container["openbook"]["title"].get("subtitle", "")
    else:
        input_data = container
        subtitle = container.get("subtitle", "")
    tags = set()
    for tag in input_data.get("subjects", []):
        name = tag["name"]
        tags.add(name)
    for cat in input_data.get("bisac",[]):
        # There's something really wrong in the tag data here, extra spaces and strange all-caps...
        for name in cat["description"].split(" / "):
            tags.add(name)
    expand_tagset(tags)

    orders = []
    if series := input_data.get("detailedSeries"):
        if (seq := series.get("readingOrder")) or seq == 0:
            order = series["seriesName"] + ' #' + str(seq)
        else:
            order = series["seriesName"]
        orders.append(order)

    creators = input_data["creators"]

    description_key = 'fullDescription' if 'fullDescription' in input_data else 'description'

    output_data = {
        "tags": sorted(tags) + mark_autoloaded,
        "series": orders,
        "title": input_data["title"],
        "authors": [creator["name"] for creator in creators if creator["role"] == 'Author'],
        "narrators": [creator["name"] for creator in creators if creator["role"] == 'Narrator'],
        "publisher": input_data["publisherAccount"]["name"],
        "description":input_data[description_key],
        "genres": []
    }
    if subtitle:
        output_data["subtitle"] = subtitle
    if genres := pick_generes_given_tags(tags):
        output_data["genres"] = genres

    # Turns out to be stored in odd places, but no problem even if it's missing.
    if 'publishDate' in input_data:
        output_data["publishedYear"] = input_data['publishDate'].split("-")[0]
    elif 'estimatedReleaseDate' in input_data:
        output_data["publishedYear"] = input_data['estimatedReleaseDate'].split("-")[0]
    else:
        for fmt in input_data["formats"]:
            if 'onSaleDateUtc' in fmt:
                output_data["publishedYear"] = input_data['estimatedReleaseDate'].split("-")[0]
                break

    if not (langs := input_data.get('languages')):
        output_data['language'] = 'English' # Presumable
    else:
        languages = set(lang["name"].title() for lang in langs)
        if languages & {'English', 'Eng', 'Xxx', ''}:
            output_data['language'] = 'English' # Presumable
        else:
            output_data['language'] = languages.pop() # pick an arbitrary one, there's probably only one

    return output_data

def genre_priority_index(tag: str) -> int | None:
    if tag in prioritized_tag_genres:
        # All of the always_genre_tags come before anything else (so they always ALL appear in the genres)
        return prioritized_tag_genres.index(tag) + 0 if tag not in always_genre_tags else -len(prioritized_tag_genres)
    return None

def pick_generes_given_tags(tag_set: Set[str]) -> List[str]:
    # Negative priority is ALWAYS a genre.
    genres = sorted( tag for tag in tag_set if (gp:=genre_priority_index(tag)) is not None and gp < 0 )
    # If there are no genres, include erasible tages like 'Fiction'; otherwise
    # include only interesting tags.
    maybe_erase = set() if not genres else erasable_tags
    prioritized = sorted( (gp, tag) for tag in (tag_set - maybe_erase) if (gp:=genre_priority_index(tag)) is not None and gp >= 0 )
    # If that turned up anything interesting, go ahead and add it.
    if prioritized:
        _, tag = prioritized[0]
        genres.append(tag)
    return genres

def expand_tagset(tags: set[str]):
    # Simple "respellings" of tags - then update to remove the "mispellings".
    new = set(normalize_tag(tag) for tag in tags)
    tags.intersection_update(new)
    tags.update(new)
    # Slightly more complex, tags implied by the presence of other tags - like
    # "Urban Fantasy" being "Fantasy" and "Urban" as well.
    new.update(itertools.chain.from_iterable((augment_tags[tag]
                                              for tag in tags
                                              if tag in augment_tags)))
    tags.clear()
    tags.update(new)

    for community, members in communities.items():
        if tags & members:
            tags.add(community)
    total = sorted(communities.keys())
    if len(tags.intersection(total)) > 1:
        # Join the tags pairwise to show the book somehow belongs to both communities.
        for i in range(len(total)):
            for j in range(i+1, len(total)):
                # For example, "FictionMixedNonfiction", always alphabetical order
                canonicalName = total[i] + "Mixed" + total[j]
                # See if we can easily say the book is almost entirely in one community.
                most = communities[total[i]] & tags
                least = communities[total[j]] & tags
                if len(most) < len(least):
                    most, least = least, most
                    j,i = i,j
                if len(least) == 0:
                    # This means we have both community tags, but one is
                    # unsupported. So get rid of it AND the overlap marker!
                    # Note: this will not get rid of the other marker, to allow
                    # the user to manually provide a marker without needing to
                    # know what specific tags moight support it.
                    tags.difference_update({total[j], canonicalName})
                    continue
                if len(least) == 1 and len(most) > len(least):
                    # Experiment: if we ignore tiny ambiguities, do we get smaller problems?
                    tags.difference_update({total[j], canonicalName})
                    continue
                tags.add(canonicalName)

# Standardize some tags that appear in both forms. This will delete the key and
# replace it with the value. Operated in normalize_tag.
canonical_tags = {
    'Alternative History': "Alternate History"
}

# These will always be placed in Genre if present, and other tags can appear
# alongside them.
always_genre_tags = {
    "Mystery",
    "Science Fiction",
    "Fantasy",
    "Historical Fiction",
    "Science",
    "History",
    "Religious Studies",
    "Philosophy",
    "Education",
    "Nature",
    "Bible Study",
}

# These will only be included in Genre if nothing else is available.
erasable_tags = {
    "Self-Help",
    "Self Improvement",
    "Self-Improvement",
    "Juvenile Literature",
    "Young Adult Literature",
    "Action & Adventure",
    "Genre Fiction",
    "Science Fiction & Fantasy",
    "Fiction",
    "Nonfiction",
    "Literature"
}

# A fairly complete list of tags that might be interesting in genres.
prioritized_tag_genres = [
    "Humor (Nonfiction)",
    "Humor (Fiction)",
    "Urban Fantasy",
    "Mystery",
    "Science Fiction",
    "Fantasy",
    "Historical Fiction",
    "Alternate History",
    "Religious Studies",
    "Nature",
    "Science",
    "History",
    "Education",
    "Bible Study",
    "Superhero",
    "Noir",
    "Crime Fiction",
    "Thriller",
    "Suspense",
    "Christianity",
    "Sociology",
    "Psychology",
    "Biblical History & Culture",
    "Christian Living",
    "Judaism",
    "Sports & Outdoors",
    "Family",
    "Religion & Spirituality",
    "Screenwriting",
    "Film & TV",
    "Arts & Entertainment",
    "Food & Wine",
    "Home & Garden",
    "Entertainment & Performing Arts",
    "Biographies & Memoirs",
    "Business & Careers",
    "Alternative & Complementary Medicine",
    "Medicine & Health Care Industry",
    "Physical Illness & Disease",
    "Health & Wellness",
    "Biography & Autobiography",
    "Nutrition",
    "Health & Fitness",
    "Medical",
    "Horror",
    "Satire",
    "Romance",
    "Ancient, Classical & Medieval Literature",
    "Data Science",
    "Mythology",
    "Philosophy",
    "Politics",
    "Computer Technology",
    "Engineering",
    "Science & Engineering",
    "Family & Relationships",
    "Anthropology",
    "Consciousness & Thought",
    "Politics & Government",
    "Parenting & Families",
    "Emotions",
    "Personal Success",
    "Relationships",
    "Technology",
    "Personal Development",
    "Self Help",
    "Military",
    "Sports & Recreations",
    "Physics",
    "New Age",
    "Language Arts",
    "Art",
    "True Crime",
    "Literary Criticism",
    "Economics",
    "Cooking & Food",
    "Travel",
    "Mathematics",
    "Finance",
    "Performing Arts",
    "Music",
    "Law",
    "Ethics",
    "Comic and Graphic Books",
    "Transportation",
    "Sales & Marketing",
    "Reference",
    "Grammar & Language Usage",
    "Gardening",
    "Foreign Language Study",
    "Folklore",
    "Essays",
    "Women's Studies",
    "Western",
    "Travel Literature",
    "Psychiatry",
    "Poetry",
    "Literary Anthologies",
    "Judaica",
    "Westerns",
    "Children",
    "Chemistry",
    "Careers",
    "Business",
    "Business & Economics",
    "Short Stories",
    "Anthologies",
    "Literary Fiction",
    "Magical Realism",
    "Humorous",
    "African American Fiction",
    "Young Adult Fiction",
    "Juvenile Nonfiction",
    "Juvenile Fiction",
    "Christian Nonfiction",
    "Christian Fiction",
    "Classic Literature",
    "World Literature",
    "Self-Help",
    "Self Improvement",
    "Self-Improvement",
    "Juvenile Literature",
    "Young Adult Literature",
    "Action & Adventure",
    "Genre Fiction",
    "Science Fiction & Fantasy",
    "Fiction",
    "Nonfiction",
    "Literature"
]

augment_tags = {
    "Urban Fantasy": {"Urban", "Fantasy"},
    "Humor (Fiction)": {"Humorous"},
    "Humor (Nonfiction)": {"Humorous"},
    "Comedy & Humor": {"Humorous"},
    "War & Military": {"Military Fiction"},
    "Crime Thrillers": {"Thriller"},
    "Domestic Thrillers": {"Thriller"},
    "Supernatural": {"Supernatural Thriller"},
    "Technothrillers": {"Thriller"},
    "Mystery & Detective": {"Mystery"},
    "Mysteries": {"Children's Mystery", "Mystery"},
    "Fantasy & Magic": {"Children's Fantasy", "Fantasy"},
    "Fitness, Diet & Nutrition": {"Health & Fitness"},
    "Cognitive Psychology & Cognition": {"Cognition"},
    "Computers & Technology": {"Computer Technology"},
    "Politics & Social Sciences": {"Sociology"},
    "Literary History & Criticism": {"Literary Criticism"},
    "Literature & Fiction": {"Fiction"},
    "Relationships, Parenting & Personal Development": {"Relationships"},
    "Travel & Tourism": {"Travel"}
}

# Found by running a graph analysis on the metadata, see scan_ladders.py.
communities = {
    # TODO: Consider adding automatic processing for exceptions?
    'Nonfiction': frozenset({'Humor (Nonfiction)', 'Christian Living', 'Social Sciences', 'Philosophy', 'International Relations', 'Science & Technology', 'Engineering', 'Judaism', 'Alternative & Complementary Medicine', 'Business & Careers', 'Ecology', 'Other Religions, Practices & Sacred Texts', 'Personal Finance', 'Systematic', 'Christology', 'Parenting & Families', 'Evolution & Genetics', 'Church & Church Leadership', 'Pneumatology', 'World', 'Religion & Spirituality', 'Business Development & Entrepreneurship', 'Middle East', 'Botany & Plants', 'Anthropology', 'Biblical History & Culture', 'Serial Killers', 'Greek & Roman', 'Management', 'Agricultural & Food Sciences', 'Expeditions & Discoveries', 'Personal Development', 'Economic', 'Evolution', 'Mathematics', 'Management & Leadership', 'Economic History', 'Money Management & Budgeting', 'Technology & Society', 'Literary History & Criticism', 'Social Issues', 'Theology', 'Physics', 'Reincarnation', 'Computers & Technology', 'Science', 'Economics', 'Medicine & Health Care Industry', 'Psychology', 'Natural History', 'Catholicism', 'Apologetics', 'Social Psychology & Interactions', 'Relationships, Parenting & Personal Development', 'Murder', 'History & Culture', 'Consciousness & Thought', 'Mental Health', 'Bible Study', 'Biology', 'Relationships', 'Meditation', 'Biblical Biography', 'Church & State', 'History & Commentary', 'Salvation Theory', 'Spiritual Growth', 'Public Policy', 'Memory Improvement', 'Essays', 'Industrial & Manufacturing', "Women's Christian Living", 'Communication & Social Skills', 'Education & Learning', 'Environmental', 'Sociology', 'Archaeology', 'Natural Resources', 'Biological Sciences', 'Study Guides', 'Environment', 'France', 'History', 'Evangelism', 'Ministry & Evangelism', 'Conservation', 'Stress Management', 'Motivation & Self-Improvement', 'Trades & Tariffs', 'Marriage & Relationships', 'Money & Finance', 'Biographies & Memoirs', 'Ecclesiology', 'New Testament', 'True Crime', 'Unexplained Mysteries', 'Future Studies', 'Death & Grief', 'Politics & Social Sciences', 'Egypt', 'Ideologies & Doctrines', 'Science & Engineering', 'Ethics', 'Nature & Ecology', 'Popular Culture', 'Civilization', 'History & Philosophy', 'Professionals & Academics', 'Personal Success', 'Saints & Sainthood', 'Aging & Longevity', 'Bibles & Bible Study', 'Science & Religion', 'Asia', 'Health & Wellness', 'Religious Studies', 'Love, Dating & Attraction', 'Travel Writing & Commentary', 'State & Local', 'Discipleship', 'Psychology & Mental Health', 'Chemistry', 'Emotions', 'Christian Eschatology', 'Programming & Software Development', 'Commentaries', 'Human Geography', 'Politics & Government', 'Data Science', 'Biotechnology', 'Career Success', 'Genetics', 'Christianity', 'Media Studies', 'Political Science', 'Metaphysics', 'Education', 'Physical Illness & Disease'}),
    'Fiction': frozenset({'Humor (Fiction)', 'Military Fiction', 'Difficult Situations', 'Gothic', 'Mystery', 'World Literature', "Women's Adventure", "Women's Fiction", 'Teen & Young Adult', 'Steampunk', 'Literature & Fiction', 'Chapter Books & Readers', 'First Contact', 'Epic', 'Contemporary', 'Police Procedurals', 'Anthologies', 'Suspense', 'Sword & Sorcery', 'Historical Fiction', 'Romantic Suspense', 'Paranormal & Urban', 'Horror', 'Gaslamp', 'Paranormal & Supernatural', 'Dramatizations', 'Supernatural', 'Private Investigators', 'Adventure', 'Science Fiction & Fantasy', 'Literary Fiction', 'Dystopian', 'Halloween', 'Superhero', 'Space Exploration', 'Fantasy', 'Westerns', 'Mash-Ups', 'Thriller & Suspense', 'Genetic Engineering', 'Hard-Boiled', 'Anthologies & Short Stories', 'Christian Fiction', 'Mysteries', 'Mystery & Suspense', 'Time Travel', 'Fairy Tales', 'Alternate History', 'Cyberpunk', 'Genre Fiction', 'Paranormal', 'Dragons & Mythical Creatures', 'Sagas', 'Science Fiction', 'Spies & Politics', 'Short Stories', 'Scary Stories', 'Ghosts', 'International Mystery & Crime', 'Biographical Fiction', 'Holidays & Celebrations', 'Crime Thrillers', 'Espionage', 'Aliens', 'Hard Science Fiction', 'Mystery, Thriller & Suspense', 'Traditional Detectives', 'American Civil War', 'Romance', 'Psychological', 'Growing Up & Facts of Life', 'Fantasy & Magic', 'Dark Humor', 'Space Opera', 'War & Military', 'Magical Realism', 'Crime Fiction', 'Technothrillers', 'Metaphysical & Visionary', 'Noir', 'Domestic Thrillers', 'Post-Apocalyptic', 'Action & Adventure'}),
}

def to_seconds(hms: str) -> int:
    parts = list(map(int, hms.split(":")))
    return sum(x * 60**i for i, x in enumerate(reversed(parts)))

def to_hms(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def main():
    if len(sys.argv) != 3:
        print("Usage: python transform_json.py <ifilename> <total_duration>")
        sys.exit(1)

    filename = sys.argv[1]
    total_duration = sys.argv[2]
    convert_file(filename, total_duration)

def convert_file(filename: str, total_duration: str):
    dir, _ = os.path.split(filename)
    ofilename = os.path.join(dir, 'metadata.json')

    total_seconds = to_seconds(total_duration)

    with open(filename, 'r') as file:
        data = json.load(file)
        input_data = data

    # Is there an Overdrive chapters list?
    chapter_file = os.path.join(dir, 'chapters.json')
    chapters = []
    if os.path.exists(chapter_file):
        # Convert to a audiobookfile chapter list.
        with open(chapter_file) as f:
            raw = json.load(f)
        # Apparently Overdrive indexes by chapter NAME, switch to a list of chapter starts.
        chs = sorted((to_seconds(time), title) for title,time in raw.items())
        for i, ch in enumerate(chs):
            if chapters:
                chapters[-1]['end'] = ch[0]
            chapters.append({'id': i, 'title': ch[1], 'start': ch[0]})
        if chapters:
            chapters[-1]['end'] = total_seconds

    output_data = abs_from_pylibby(input_data, ["Autoloaded", "OdmpyNG"])
    if chapters:
        output_data['chapters'] = chapters

    with open(ofilename, 'w') as f:
        json.dump(output_data, f, indent=2)

if __name__ == "__main__":
    main()
