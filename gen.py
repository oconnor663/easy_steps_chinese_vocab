#! /usr/bin/env python3

from collections import namedtuple
import genanki
import os.path as path
import sys

DictEntry = namedtuple("DictEntry",
                       ["simp", "trads", "pinyins", "definitions"])

ACCENTS = {
    "1": "\u0304",
    "2": "\u0301",
    "3": "\u030C",
    "4": "\u0300",
}

ACCENT_TARGETS = [
    "a",
    "e",
    "i",
    "o",
    # This is subtle. We want accent markers to go *after* colons (which are
    # going to get directly replaced with umlaut markers later), so that
    # character rendering puts them on top. The easiest way to achieve this is
    # to target the colon with higher precedence than the "u".
    ":",
    "u",
]

UMLAUT = "\u0308"


def find_accent_index(part):
    lowerpart = part.lower()
    for c in ACCENT_TARGETS:
        i = lowerpart.find(c)
        if i != -1:
            # +1 because the combining character goes after
            return i + 1
    return -1


def format_umlaut(part):
    # Unicode combining characters go after the character they combine with, so
    # a straight replacement is good enough for this case. (Unlike the tone
    # marker, where we need to search for the right vowel to mark.)
    return part.replace(":", UMLAUT)


def format_pinyin(pinyin):
    # Pinyin for proper nouns tends to be uppercased. lower() normalizes that.
    parts = pinyin.lower().split()
    new_parts = []
    for part in parts:
        if part[-1] in ("1", "2", "3", "4"):
            i = find_accent_index(part)
            if i != -1:
                accent = ACCENTS[part[-1]]
                # Insert the accent and drop the number at the end.
                new_parts.append(part[:i] + accent + part[i:-1])
            else:
                # There are a few cases like "m2" for an interjection.
                new_parts.append(part)
        elif part[-1] == "5":
            # This is the neutral tone. Just drop the 5.
            new_parts.append(part[:-1])
        else:
            new_parts.append(part)
    return format_umlaut(" ".join(new_parts))


def parse_rest(rest):
    assert rest[0] == "["
    [pinyin, slash_defs] = rest[1:].split("]", 1)
    # The "CL:" definitions are about classifiers, and they're too noisy.
    definitions = [
        d.strip() for d in slash_defs.split("/") if d and not d.isspace()
    ]
    return (pinyin, definitions)


def filter_definitions(definitions):
    ret = []
    # Filter out definitions that tend to add too much noise. If none are left,
    # the caller will drop this entry entirely.
    bad_prefixes = [
        "variant of ",
        "old variant of ",
        "CL:",
    ]
    for d in definitions:
        if any(d.startswith(prefix) for prefix in bad_prefixes):
            continue
        ret.append(d)
    return ret


def load_cedict():
    dict_path = path.join(path.dirname(__file__), "cc_cedict.txt")
    with open(dict_path) as f:
        d = {}
        for line in f:
            if line.startswith("#"):
                continue
            trad, simp, rest = line.split(" ", 2)
            unformatted_pinyin, unfiltered_definitions = parse_rest(rest)
            if unformatted_pinyin[0].isupper():
                # Skip proper nouns.
                continue
            definitions = filter_definitions(unfiltered_definitions)
            if not definitions:
                # All the definitions in this line got filtered out. Skip it.
                continue
            pinyin = format_pinyin(unformatted_pinyin)
            entry = d.get(simp)
            if not entry:
                entry = DictEntry(simp, [trad], [pinyin], definitions)
                d[simp] = entry
            else:
                if trad not in entry.trads:
                    entry.trads.append(trad)
                if pinyin not in entry.pinyins:
                    entry.pinyins.append(pinyin)
                entry.definitions.extend(definitions)
    return d


CSS = """\
.card {
    font-size: 32px;
    font-family: arial;
    text-align: center;
}

.hanzi {
    font-size: 64px;
}

.traditional {
    font-size: 48px;
}
"""

QFMT1 = """<span class="hanzi">{{Simplified}}</span>"""
AFMT1 = """\
<span class="hanzi">{{SimpAndTrad}}</span>
<hr id="answer">
{{Pinyin}}
<hr>
{{Definition}}
"""

QFMT2 = """{{Definition}}"""
AFMT2 = """\
{{Definition}}
<hr id="answer">
<span class="hanzi">{{SimpAndTrad}}</span>
<hr>
{{Pinyin}}
"""


class EasyStepsNote(genanki.Note):
    @property
    def guid(self):
        # Only use the simplified hanzi as a card identifier.
        return genanki.guid_for(self.fields[0])


def make_model(deck_id):
    return genanki.Model(
        deck_id + 1,
        'Easy Steps Model',
        fields=[
            # This field is used for the stable ID of the card.
            {
                'name': 'Simplified'
            },
            # This field is used for display. It's formatting can change.
            {
                'name': 'SimpAndTrad'
            },
            {
                'name': 'Pinyin'
            },
            {
                'name': 'Definition'
            },
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': QFMT1,
                'afmt': AFMT1,
            },
            {
                'name': 'Card 2',
                'qfmt': QFMT2,
                'afmt': AFMT2,
            },
        ],
        css=CSS,
    )


def split_line(line):
    return [part.strip() for part in line.split("|")]


def parse_text(text):
    lines = text.splitlines()
    [deck_name, deck_id_str] = split_line(lines[0])
    notes = [
        split_line(line) for line in lines[1:]
        if line.strip() and not line.startswith("#")
    ]
    return deck_name, int(deck_id_str), notes


def format_hanzi(simp, trads):
    dashed_trads = []
    for trad in trads:
        if trad == simp:
            continue
        dashed = ""
        assert (len(simp) == len(trad)
                ), "is {} really the traditional form of {}?".format(
                    repr(simp), repr(trad))
        for i in range(len(simp)):
            if simp[i] == trad[i]:
                dashed += "-"
            else:
                dashed += trad[i]
        dashed_trads.append(dashed)
    if dashed_trads:
        return (simp + """<hr><span class="traditional">""" +
                " / ".join(dashed_trads) + "</span>")
    else:
        return simp


def make_deck(deck_name, deck_id, notes, cedict):
    deck = genanki.Deck(deck_id, deck_name)
    model = make_model(deck_id)
    for note in notes:
        simp = note[0]
        if len(note) == 1:
            entry = cedict.get(simp)
            if not entry:
                print("NEEDS DEFINITION:", simp)
                continue
            trads = entry.trads
            pinyins = entry.pinyins
            definitions = entry.definitions
        else:
            assert len(note) == 3
            trads = []
            pinyins = [format_pinyin(note[1])]
            definitions = [note[2]]
        fields = [
            simp,
            format_hanzi(simp, trads),
            ", ".join(pinyins),
            " / ".join(definitions),
        ]
        # print(fields)
        deck.add_note(EasyStepsNote(model=model, fields=fields))
    return deck


def main():
    cedict = load_cedict()
    input_path = sys.argv[1]
    text = open(input_path).read()
    deck_name, deck_id, notes = parse_text(text)
    deck = make_deck(deck_name, deck_id, notes, cedict)
    output_path = path.splitext(input_path)[0] + ".apkg"
    genanki.Package(deck).write_to_file(output_path)
    print("created", output_path)


if __name__ == "__main__":
    main()
