# -*- coding: utf-8 -*-

import ast
import glob
import os.path as osp
import types

import pytest
from PIL import Image

from pibooth import pictures
from pibooth_template_chooser import setup_template_factory
from pibooth_template_chooser.template import TemplateParser, TemplateParserError, TemplatePictureFactory
from pibooth_template_chooser import BUNDLED_TEMPLATES
from conftest import CAPTURE_COLOR

TEMPLATE = osp.join(BUNDLED_TEMPLATES, 'photomaton.xml')


@pytest.fixture
def parser():
    return TemplateParser(TEMPLATE)


def test_parser_reads_one_page_per_capture_number(parser):
    assert parser.get_size(4, pictures.PORTRAIT) == (1182, 1749)
    assert parser.get_size(1, pictures.LANDSCAPE) == (1749, 1182)
    assert len(parser.get_capture_rects(4, pictures.PORTRAIT)) == 8  # Two strips
    assert len(parser.get_text_rects(1, pictures.LANDSCAPE)) == 2


def test_parser_rejects_a_missing_page(parser):
    with pytest.raises(TemplateParserError):
        parser.get_size(2, pictures.PORTRAIT)


def test_best_orientation_follows_the_available_page(parser, capture):
    assert parser.get_best_orientation([capture]) == pictures.LANDSCAPE
    assert parser.get_best_orientation([capture] * 4) == pictures.PORTRAIT


def test_factory_draws_captures_and_centered_text(parser, capture):
    factory = TemplatePictureFactory(parser, pictures.LANDSCAPE, capture)
    factory.add_text('Hello', 'Amatic-Bold', (0, 0, 255), 'center')

    image = factory.build()

    assert image.getpixel((873, 496))[:3] == CAPTURE_COLOR
    # The text holder spans x 96..1650, y 945..1050: ink centered in it
    text_box = image.crop((96, 945, 1650, 1050)).convert('RGB')
    ink = [(x, y) for x in range(text_box.width) for y in range(text_box.height)
           if text_box.getpixel((x, y))[2] > 200 and text_box.getpixel((x, y))[0] < 100]
    xs, ys = [p[0] for p in ink], [p[1] for p in ink]
    assert abs((min(xs) + max(xs)) / 2 - text_box.width / 2) < 5
    assert abs((min(ys) + max(ys)) / 2 - text_box.height / 2) < 5


def test_hook_uses_the_configured_template(cfg, capture):
    cfg.set('PICTURE', 'template', TEMPLATE)
    default = pictures.get_picture_factory((capture,))

    factory = setup_template_factory(cfg, default)

    assert isinstance(factory, TemplatePictureFactory)
    assert factory.orientation == pictures.LANDSCAPE
    assert setup_template_factory(cfg, default).template is factory.template  # parsed once


def test_hook_keeps_the_standard_layout_without_template(cfg, capture):
    assert setup_template_factory(cfg, pictures.get_picture_factory((capture,))) is None


def test_every_bundled_template_parses_with_its_style():
    from pibooth_template_chooser.chooser import TemplateChoice
    paths = sorted(glob.glob(osp.join(BUNDLED_TEMPLATES, '*.xml')))

    choices = [TemplateChoice(path) for path in paths]

    assert len(choices) == 9
    for choice in choices:
        assert choice.style, choice.path  # Every bundled template has a style file
        for font in ast.literal_eval(choice.style['text_fonts']):
            assert not font.endswith('.ttf') or osp.isfile(font), font


def test_startup_offers_the_bundled_templates_by_default(cfg):
    from pibooth_template_chooser import pibooth_startup
    cfg.set('TEMPLATE_CHOOSER', 'directory', '')
    app = types.SimpleNamespace(previous_picture=None)

    pibooth_startup(cfg, app)

    assert len(app.template_chooser.choices) == 9
    assert app.previous_picture is app.template_chooser.current.placeholder
