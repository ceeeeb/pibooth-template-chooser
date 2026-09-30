"""Generate a pibooth-picture-template file for a Canon SELPHY postcard (100 x 148 mm).

Units are hundredths of an inch, as in draw.io. At 300 dpi the page renders at
the SELPHY resolution.
"""

import sys

MM = 100 / 25.4  # draw.io units per millimetre
CARD_SHORT, CARD_LONG = 100 * MM, 148 * MM

CAPTURE_STYLE = "rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
TEXT_STYLE = "text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;"


class Page:

    def __init__(self, name, width, height):
        self.name, self.width, self.height = name, width, height
        self.cells = []

    def add(self, value, style, x, y, width, height):
        self.cells.append((value, style, x, y, width, height))

    def xml(self, page_id):
        cells = ['<mxCell id="0" dpi="300"/>', '<mxCell id="1" parent="0"/>']
        for index, (value, style, x, y, width, height) in enumerate(self.cells, 2):
            cells.append(
                '<mxCell id="{}-{}" value="{}" style="{}" vertex="1" parent="1">'
                '<mxGeometry x="{:.0f}" y="{:.0f}" width="{:.0f}" height="{:.0f}" as="geometry"/>'
                '</mxCell>'.format(page_id, index, value, style, x, y, width, height))
        return ('<diagram id="{}" name="{}"><mxGraphModel dx="800" dy="600" grid="1" gridSize="5" '
                'page="1" pageScale="1" pageWidth="{:.0f}" pageHeight="{:.0f}"><root>{}</root>'
                '</mxGraphModel></diagram>').format(page_id, self.name, self.width, self.height, "".join(cells))


def photo_strips():
    """Two identical photo booth strips side by side, to cut in the middle."""
    page = Page("4 photos - bandes photomaton", CARD_SHORT, CARD_LONG)
    strip_width = CARD_SHORT / 2
    margin, gap = 4 * MM, 2.5 * MM
    capture_width = strip_width - 2 * margin
    capture_height = capture_width * 2 / 3
    for strip in range(2):
        left = strip * strip_width + margin
        for number in range(1, 5):
            top = margin + (number - 1) * (capture_height + gap)
            page.add(str(number), CAPTURE_STYLE, left, top, capture_width, capture_height)
        text_top = top + capture_height + 3 * MM
        page.add("footer_text1", TEXT_STYLE, left, text_top, capture_width, 9 * MM)
        page.add("footer_text2", TEXT_STYLE, left, text_top + 9 * MM, capture_width, 6 * MM)
    return page


def single_photo():
    """One large photo on a landscape postcard, texts underneath."""
    page = Page("1 photo", CARD_LONG, CARD_SHORT)
    margin = 5 * MM
    capture_height = CARD_SHORT - 2 * margin - 16 * MM
    capture_width = capture_height * 16 / 9
    left = (CARD_LONG - capture_width) / 2
    page.add("1", CAPTURE_STYLE, left, margin, capture_width, capture_height)
    text_top = margin + capture_height + 1 * MM
    page.add("footer_text1", TEXT_STYLE, left, text_top, capture_width, 9 * MM)
    page.add("footer_text2", TEXT_STYLE, left, text_top + 9 * MM, capture_width, 5 * MM)
    return page


pages = [photo_strips(), single_photo()]
diagrams = "".join(page.xml("page{}".format(i)) for i, page in enumerate(pages, 1))
content = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<mxfile host="app.diagrams.net" type="device" pages="{}">{}</mxfile>\n').format(len(pages), diagrams)
with open(sys.argv[1], "w") as fp:
    fp.write(content)
