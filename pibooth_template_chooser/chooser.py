# -*- coding: utf-8 -*-

"""Templates guests choose from, and previews of the last picture in them.

A template may come with a style file of the same name (``hollywood.xml`` and
``hollywood.cfg``) giving its displayed name and the fonts and colors of its
texts::

    [TEMPLATE]
    name = Hollywood
    text_colors = ((255, 255, 255), (230, 200, 205))
    text_fonts = ('../fonts/Montserrat-Bold.ttf', '../fonts/Montserrat-SemiBold.ttf')

Relative font paths are resolved from the style file directory.
"""

import ast
import base64
import os.path as osp
from configparser import ConfigParser
from io import BytesIO

from PIL import Image, ImageDraw

from pibooth.utils import LOGGER

from .template import TemplateParser, TemplatePictureFactory, TemplateShapeParser

STYLED_OPTIONS = ('text_colors', 'text_fonts', 'text_alignments')
PLACEHOLDER_SIZE = 1200


class TemplateChoice(object):

    """A template file, its parsed layout and its text style."""

    def __init__(self, path):
        self.path = path
        self.parser = TemplateParser(path)
        self.name = osp.splitext(osp.basename(path))[0].replace('-', ' ').capitalize()
        self.style = {}
        style_path = osp.splitext(path)[0] + '.cfg'
        if osp.isfile(style_path):
            self._read_style(style_path)
        self.placeholder = render_placeholder(self.parser)

    def _read_style(self, style_path):
        style = ConfigParser()
        style.read(style_path, encoding='utf-8')
        if not style.has_section('TEMPLATE'):
            return
        self.name = style.get('TEMPLATE', 'name', fallback=self.name)
        for option in STYLED_OPTIONS:
            if style.has_option('TEMPLATE', option):
                self.style[option] = style.get('TEMPLATE', option)
        if 'text_fonts' in self.style:
            self.style['text_fonts'] = resolve_fonts(self.style['text_fonts'], osp.dirname(style_path))


def resolve_fonts(value, directory):
    """Make the relative font paths of a style file absolute."""
    fonts = ast.literal_eval(value)
    if isinstance(fonts, str):
        fonts = (fonts,)
    resolved = []
    for font in fonts:
        candidate = osp.normpath(osp.join(directory, font))
        resolved.append(candidate if not osp.isabs(font) and osp.isfile(candidate) else font)
    return str(tuple(resolved))


def render_placeholder(parser):
    """Draw the page of the smallest capture number, the one guests are shown
    until a picture exists: embedded images as they are, capture holders in grey.
    """
    orientation, number = min(((orientation, number) for orientation, pages in parser.data.items()
                               for number in pages), key=lambda item: item[1])
    width, height = parser.get_size(number, orientation)
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for shape in parser.get_rects(number, orientation):
        box = (shape.x, shape.y, shape.x + shape.width, shape.y + shape.height)
        if shape.type == TemplateShapeParser.TYPE_IMAGE:
            data = base64.b64decode(shape.image.split(',', 1)[1])
            picture = Image.open(BytesIO(data)).convert('RGBA').resize((shape.width, shape.height))
            image.paste(picture, box[:2], picture)
        elif shape.type == TemplateShapeParser.TYPE_CAPTURE:
            draw.rectangle(box, fill=(170, 170, 175))
    image.thumbnail((PLACEHOLDER_SIZE, PLACEHOLDER_SIZE))
    return image


class TemplateChooser(object):

    """Keep the list of templates and apply the selected one to the configuration."""

    def __init__(self, cfg, choices):
        self.cfg = cfg
        self.choices = choices
        self.defaults = {option: cfg.get('PICTURE', option) for option in STYLED_OPTIONS}
        current = cfg.getpath('PICTURE', 'template')
        paths = [choice.path for choice in choices]
        self.index = paths.index(current) if current in paths else 0
        self.apply()

    @property
    def current(self):
        return self.choices[self.index]

    def select(self, step):
        self.index = (self.index + step) % len(self.choices)
        self.apply()
        LOGGER.info("Template selected: %s", self.current.name)

    def apply(self):
        """Make the selected template the one of the next pictures, and set
        its text style (or restore the configured one)."""
        choice = self.current
        self.cfg.set('PICTURE', 'template', choice.path)
        self.cfg.template = choice.parser
        for option in STYLED_OPTIONS:
            self.cfg.set('PICTURE', option, choice.style.get(option, self.defaults[option]))


class Preview(object):

    """First capture and texts of the last picture, assembled again in the
    single photo page of any template to show guests what they choose. The
    capture is kept after the other plugins processed it (background removal),
    so previews cost no processing."""

    MAX_CAPTURE_WIDTH = 1600

    def __init__(self):
        self.images = self.texts = None
        self.opt_index = 0
        self.cache = {}
        self.waiting = False

    def expect(self):
        """Keep the next picture factory, the one of the final picture."""
        self.waiting = True

    def store(self, factory, opt_index):
        self.waiting = False
        self.images = [self._reduce(factory._images[0])]
        self.texts = [text[0] for text in factory._texts]
        self.opt_index = opt_index
        self.cache = {}

    def _reduce(self, image):
        image = image.copy()
        image.thumbnail((self.MAX_CAPTURE_WIDTH, self.MAX_CAPTURE_WIDTH))
        return image

    def build(self, choice, cfg):
        """Return the last capture assembled in the given template, its
        placeholder while no picture exists, or None if it can not be built."""
        if not self.images:
            return choice.placeholder
        if choice.path not in self.cache:
            try:
                self.cache[choice.path] = self._assemble(choice.parser, cfg)
            except Exception as ex:  # No page for this capture number, broken template...
                LOGGER.warning("No preview of template '%s': %s", choice.name, ex)
                self.cache[choice.path] = None
        return self.cache[choice.path]

    def _assemble(self, parser, cfg):
        orientation = parser.get_best_orientation(self.images)
        factory = TemplatePictureFactory(parser, orientation, *self.images)
        factory.set_background(cfg.gettuple('PICTURE', 'backgrounds', ('color', 'path'), 2)[self.opt_index])
        if cfg.getboolean('PICTURE', 'captures_cropping'):
            factory.set_cropping()
        count = len(self.texts)
        styles = zip(self.texts, cfg.gettuple('PICTURE', 'text_fonts', str, count),
                     cfg.gettuple('PICTURE', 'text_colors', 'color', count),
                     cfg.gettuple('PICTURE', 'text_alignments', str, count))
        for text, font, color, align in styles:
            if text:
                factory.add_text(text, font, color, align)
        return factory.build()
