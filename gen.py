#! /usr/bin/env python3

import genanki
import os
import sys

CSS = """\
.card {
    font-size: 40px;
    text-align: center;
}

.hanzi {
    font-size: 80px;
}
"""

QFMT1 = """<span class="hanzi">{{Hanzi}}</span>"""
AFMT1 = """\
{{FrontSide}}
<hr id="answer">{{Pinyin}}
<hr>{{Definition}}
"""

QFMT2 = """{{Definition}}"""
AFMT2 = """\
{{FrontSide}}
<hr id="answer"><span class="hanzi">{{Hanzi}}</span>
<hr>{{Pinyin}}
"""


class EasyStepsNote(genanki.Note):
    @property
    def guid(self):
        # Only use the hanzi as a card identifier.
        return genanki.guid_for(self.fields[0])


def make_model(deck_id):
    return genanki.Model(
        deck_id + 1,
        'Easy Steps Model',
        fields=[
            {
                'name': 'Hanzi'
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


def main():
    input_path = sys.argv[1]
    text = open(input_path).read()
    deck_name, deck_id, notes = parse_text(text)
    deck = genanki.Deck(deck_id, deck_name)
    model = make_model(deck_id)
    for note in notes:
        deck.add_note(EasyStepsNote(model=model, fields=note))
    output_path = os.path.splitext(input_path)[0] + ".apkg"
    genanki.Package(deck).write_to_file(output_path)
    print("created", output_path)


if __name__ == "__main__":
    main()
