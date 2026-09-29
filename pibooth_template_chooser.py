# -*- coding: utf-8 -*-

"""Pibooth plugin letting guests choose the picture template on the wait screen.

The templates are the draw.io files of the ``pibooth-picture-template`` plugin,
read from a directory. A template may come with a style file of the same name
(``hollywood.xml`` and ``hollywood.cfg``) giving its displayed name and the
fonts and colors of its texts::

    [TEMPLATE]
    name = Hollywood
    text_colors = ((255, 255, 255), (230, 200, 205))
    text_fonts = ('../fonts/Montserrat-Bold.ttf', '../fonts/Montserrat-SemiBold.ttf')

Relative font paths are resolved from the style file directory.
"""

import ast
import base64
import glob
import os.path as osp
from configparser import ConfigParser
from io import BytesIO

import pygame
from PIL import Image, ImageDraw

import pibooth
from pibooth.utils import LOGGER
from pibooth_picture_template import TemplateParser, TemplatePictureFactory, TemplateShapeParser

__version__ = "1.0.0"

SECTION = 'TEMPLATE_CHOOSER'
STYLED_OPTIONS = ('text_colors', 'text_fonts', 'text_alignments')
BANNER_HEIGHT_RATIO = 0.14
# A horizontal move longer than this share of the screen width is a swipe
SWIPE_RATIO = 0.08
PREVIOUS_KEYS = (pygame.K_UP, pygame.K_LEFT)
NEXT_KEYS = (pygame.K_DOWN, pygame.K_RIGHT)


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
        self.thumbnail = render_thumbnail(self.parser)

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


def render_thumbnail(parser):
    """Draw the page of the smallest capture number, the one guests are shown:
    embedded images as they are, capture holders in grey.
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
    image.thumbnail((400, 400))
    return pygame.image.frombytes(image.tobytes(), image.size, 'RGB')


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
        """Point the picture-template plugin to the selected template, and
        set its text style (or restore the configured one)."""
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
        """Return the last captures assembled in the given template, or None."""
        if not self.images:
            return None
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


class Banner(object):

    """Template selector drawn at the top of the wait screen."""

    def __init__(self):
        self.previous_rect = self.next_rect = self.rect = None

    def layout(self, surface_rect):
        height = int(surface_rect.height * BANNER_HEIGHT_RATIO)
        self.rect = pygame.Rect(0, 0, surface_rect.width, height)
        button = int(height * 0.7)
        margin = (height - button) // 2
        self.previous_rect = pygame.Rect(margin, margin, button, button)
        self.next_rect = pygame.Rect(surface_rect.width - margin - button, margin, button, button)

    def draw(self, surface, chooser):
        self.layout(surface.get_rect())
        background = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        background.fill((0, 0, 0, 190))
        surface.blit(background, self.rect.topleft)
        for rect, label in ((self.previous_rect, '<'), (self.next_rect, '>')):
            self._draw_button(surface, rect, label)
        self._draw_choice(surface, chooser)

    def _draw_button(self, surface, rect, label):
        pygame.draw.rect(surface, (70, 70, 70), rect, border_radius=8)
        pygame.draw.rect(surface, (150, 150, 150), rect, 2, border_radius=8)
        text = pygame.font.Font(None, int(rect.height * 0.9)).render(label, True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=rect.center))

    def _draw_choice(self, surface, chooser):
        height = int(self.rect.height * 0.8)
        thumbnail = chooser.current.thumbnail
        width = int(thumbnail.get_width() * height / thumbnail.get_height())
        thumbnail = pygame.transform.smoothscale(thumbnail, (width, height))
        name = pygame.font.Font(None, int(self.rect.height * 0.42)).render(
            "{}  ({}/{})".format(chooser.current.name, chooser.index + 1, len(chooser.choices)), True, (255, 255, 255))
        total = width + 20 + name.get_width()
        x = self.rect.centerx - total // 2
        top = (self.rect.height - height) // 2
        surface.blit(thumbnail, (x, top))
        pygame.draw.rect(surface, (255, 255, 255), (x - 2, top - 2, width + 4, height + 4), 2)
        surface.blit(name, name.get_rect(midleft=(x + width + 20, self.rect.centery)))

    def step_for(self, pos):
        """Return -1 or 1 if the position hits a button, 0 inside the banner,
        None outside of it."""
        if self.previous_rect.collidepoint(pos):
            return -1
        if self.next_rect.collidepoint(pos):
            return 1
        return 0 if self.rect.collidepoint(pos) else None


def event_position(event, surface):
    if event.type in (pygame.FINGERDOWN, pygame.FINGERUP):
        width, height = surface.get_size()
        return (event.x * width, event.y * height)
    return event.pos


def is_touch(event):
    return (event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and event.button in (1, 2, 3)) \
        or event.type in (pygame.FINGERDOWN, pygame.FINGERUP)


class Swipe(object):

    """Track a touch from press to release to recognize horizontal swipes."""

    def __init__(self):
        self.start = None

    def press(self, pos):
        self.start = pos

    def release(self, pos, width):
        """Return 1 for a swipe to the left (next), -1 to the right, 0 otherwise."""
        start, self.start = self.start, None
        if start is None:
            return 0
        dx, dy = pos[0] - start[0], pos[1] - start[1]
        if abs(dx) < width * SWIPE_RATIO or abs(dx) < abs(dy):
            return 0
        return 1 if dx < 0 else -1


def selection_step(banner, swipe, surface, events):
    """Return the requested move in the template list (arrow keys, swipe,
    banner buttons). The touches used for it are consumed so that they trigger
    no capture; a simple tap elsewhere keeps its pibooth meaning."""
    if banner.rect is None:
        banner.layout(surface.get_rect())
    step, consumed = 0, []
    for event in events:
        if event.type == pygame.KEYDOWN and event.key in PREVIOUS_KEYS + NEXT_KEYS:
            step += -1 if event.key in PREVIOUS_KEYS else 1
            consumed.append(event)
        elif is_touch(event):
            pos = event_position(event, surface)
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                swipe.press(pos)
                continue
            swiped = swipe.release(pos, surface.get_width())
            touched = banner.step_for(pos)
            if swiped or touched is not None:
                step += swiped or touched
                consumed.append(event)
    for event in consumed:
        events.remove(event)
    return step


@pibooth.hookimpl
def pibooth_configure(cfg):
    cfg.add_option(SECTION, 'directory', '~/.config/pibooth/templates',
                   "Directory of the picture templates guests choose from on the wait screen")


@pibooth.hookimpl
def pibooth_startup(cfg, app):
    paths = sorted(glob.glob(osp.join(cfg.getpath(SECTION, 'directory'), '*.xml')))
    choices = []
    for path in paths:
        try:
            choices.append(TemplateChoice(path))
        except Exception as ex:  # A broken template must not prevent the others
            LOGGER.warning("Template '%s' ignored: %s", path, ex)
    app.template_chooser = TemplateChooser(cfg, choices) if choices else None
    app.template_banner = Banner()
    app.template_swipe = Swipe()
    app.template_preview = Preview()
    cfg.template_preview = app.template_preview  # The factory hook only receives cfg
    LOGGER.info("Template chooser: %s templates", len(choices))


@pibooth.hookimpl
def state_wait_validate(app):
    """Enter the wait state again so that every plugin redraws the screen
    around the new preview (picture, gallery QR code...)."""
    if getattr(app, 'template_redraw', False):
        app.template_redraw = False
        return 'wait'


@pibooth.hookimpl
def state_processing_enter(app):
    if getattr(app, 'template_chooser', None):
        app.template_preview.expect()


@pibooth.hookimpl(hookwrapper=True, tryfirst=True)
def pibooth_setup_picture_factory(cfg, opt_index, factory):
    """Keep the captures and texts of the final picture, once the other
    plugins have set them up: as the outermost wrapper, this one resumes last,
    after pibooth added the texts. The next calls build animation frames."""
    outcome = yield
    preview = getattr(cfg, 'template_preview', None)
    if preview and preview.waiting:
        preview.store(outcome.get_result(), opt_index)


@pibooth.hookimpl(hookwrapper=True)
def state_wait_do(cfg, app, win, events):
    """Handle the selection before the other plugins see the events, and draw
    the banner once they have drawn the screen."""
    chooser = getattr(app, 'template_chooser', None)
    if chooser:
        step = selection_step(app.template_banner, app.template_swipe, win.surface, events)
        if step:
            chooser.select(step)
            preview = app.template_preview.build(chooser.current, cfg)
            if preview:
                # Displayed only: the saved and printed file is the real picture
                app.previous_picture = preview
                app.previous_animated = None
                app.template_redraw = True
    yield
    if chooser:
        app.template_banner.draw(win.surface, chooser)
        pygame.display.update()
