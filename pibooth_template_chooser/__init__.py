# -*- coding: utf-8 -*-

"""Pibooth plugin letting guests choose the picture template on the wait screen.

The templates are draw.io files read from a directory, see ``template.py``
for their format and ``chooser.py`` for their optional style file.
"""

import glob
import os.path as osp

import pygame

import pibooth
from pibooth import pictures
from pibooth.utils import LOGGER

from .chooser import Preview, TemplateChoice, TemplateChooser
from .template import TemplateParser, TemplatePictureFactory
from .touch import Caption, Swipe, selection_step

__version__ = "2.1.0"

SECTION = 'TEMPLATE_CHOOSER'
BUNDLED_TEMPLATES = osp.join(osp.dirname(osp.abspath(__file__)), 'templates')


@pibooth.hookimpl
def pibooth_configure(cfg):
    cfg.add_option('PICTURE', 'template', '',
                   "Picture template path (draw.io file), empty for the standard layout")
    cfg.add_option(SECTION, 'directory', '',
                   "Directory of the picture templates guests choose from on the wait screen, "
                   "empty for the templates shipped with the plugin")


@pibooth.hookimpl
def pibooth_startup(cfg, app):
    directory = cfg.getpath(SECTION, 'directory') or BUNDLED_TEMPLATES
    paths = sorted(glob.glob(osp.join(directory, '*.xml')))
    choices = []
    for path in paths:
        try:
            choices.append(TemplateChoice(path))
        except Exception as ex:  # A broken template must not prevent the others
            LOGGER.warning("Template '%s' ignored: %s", path, ex)
    app.template_chooser = TemplateChooser(cfg, choices) if choices else None
    app.template_caption = Caption()
    app.template_swipe = Swipe()
    app.template_preview = Preview()
    cfg.template_preview = app.template_preview  # The factory hook only receives cfg
    LOGGER.info("Template chooser: %s templates", len(choices))
    if app.template_chooser and app.previous_picture is None:
        app.previous_picture = app.template_chooser.current.placeholder


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


@pibooth.hookimpl(specname='pibooth_setup_picture_factory')
def setup_template_factory(cfg, factory):
    """Assemble the picture in the selected template, if any."""
    path = cfg.getpath('PICTURE', 'template')
    if not path:
        return None
    if getattr(cfg, 'template', None) is None or cfg.template.filename != path:
        cfg.template = TemplateParser(path)
    orientation = cfg.get('PICTURE', 'orientation')
    if orientation == pictures.AUTO:
        orientation = cfg.template.get_best_orientation(factory._images)
    return TemplatePictureFactory(cfg.template, orientation, *factory._images)


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
    the caption once they have drawn the screen, until it expires."""
    chooser = getattr(app, 'template_chooser', None)
    caption = getattr(app, 'template_caption', None)
    if chooser:
        step = selection_step(caption, app.template_swipe, win.surface, events,
                              cfg.getboolean('WINDOW', 'touch_flip'))
        if step:
            chooser.select(step)
            caption.show()
            preview = app.template_preview.build(chooser.current, cfg)
            if preview:
                # Displayed only: the saved and printed file is the real picture
                app.previous_picture = preview
                app.previous_animated = None
                app.template_redraw = True
    yield
    if not chooser:
        return
    if app.previous_picture is None:
        # The last picture was discarded (forget button): never preview it
        app.template_preview.clear()
        app.previous_picture = chooser.current.placeholder
        app.template_redraw = True
    if not caption.expired:
        caption.draw(win.surface, chooser)
        pygame.display.update()
    elif caption.drawn:
        caption.hide()
        app.template_redraw = True  # Redraw the screen without the caption
