# -*- coding: utf-8 -*-

import ast
import types

import pygame
import pytest
from PIL import Image

from pibooth_template_chooser import (Caption, Preview, Swipe, TemplateChoice, TemplateChooser,
                                      resolve_fonts, selection_step)
from conftest import CAPTURE_COLOR


def test_resolve_fonts_makes_existing_relative_paths_absolute(tmp_path):
    (tmp_path / 'fonts').mkdir()
    (tmp_path / 'fonts' / 'Title.ttf').write_bytes(b'')

    resolved = ast.literal_eval(resolve_fonts("('fonts/Title.ttf', 'Amatic-Bold', 'fonts/Missing.ttf')", str(tmp_path)))

    assert resolved == (str(tmp_path / 'fonts' / 'Title.ttf'), 'Amatic-Bold', 'fonts/Missing.ttf')


def test_resolve_fonts_accepts_a_single_font(tmp_path):
    assert ast.literal_eval(resolve_fonts("'Amatic-Bold'", str(tmp_path))) == ('Amatic-Bold',)


def test_choice_reads_its_style_file(templates_dir):
    choice = TemplateChoice(str(templates_dir / 'photomaton.xml'))

    assert choice.name == 'Photomaton'
    assert choice.style['text_colors'] == '((0, 0, 0), (90, 90, 90))'
    assert str(templates_dir / 'fonts' / 'Title.ttf') in choice.style['text_fonts']


def test_choice_without_style_is_named_after_its_file(templates_dir):
    choice = TemplateChoice(str(templates_dir / 'second.xml'))

    assert choice.name == 'Second'
    assert choice.style == {}


def test_placeholder_shows_the_single_photo_page(templates_dir):
    placeholder = TemplateChoice(str(templates_dir / 'photomaton.xml')).placeholder

    # Landscape page of 1749x1182 px reduced to fit 1200 px, capture holder in grey
    assert placeholder.size == (1200, 811)
    assert placeholder.getpixel((600, 340)) == (170, 170, 175)
    assert placeholder.getpixel((5, 5)) == (255, 255, 255)


def make_chooser(cfg, templates_dir):
    choices = [TemplateChoice(str(templates_dir / name)) for name in ('photomaton.xml', 'second.xml')]
    return TemplateChooser(cfg, choices)


def test_chooser_starts_on_the_configured_template(cfg, templates_dir):
    cfg.set('PICTURE', 'template', str(templates_dir / 'second.xml'))

    assert make_chooser(cfg, templates_dir).current.name == 'Second'


def test_chooser_applies_the_style_and_restores_the_configured_one(cfg, templates_dir):
    cfg.set('PICTURE', 'text_colors', '(255, 0, 0)')
    chooser = make_chooser(cfg, templates_dir)

    assert cfg.get('PICTURE', 'text_colors') == '((0, 0, 0), (90, 90, 90))'
    assert cfg.template is chooser.current.parser

    chooser.select(1)

    assert cfg.get('PICTURE', 'template') == str(templates_dir / 'second.xml')
    assert cfg.get('PICTURE', 'text_colors') == '(255, 0, 0)'


def test_chooser_wraps_around(cfg, templates_dir):
    chooser = make_chooser(cfg, templates_dir)

    chooser.select(-1)

    assert chooser.current.name == 'Second'


class FakeFactory(object):

    def __init__(self, capture, texts):
        self._images = [capture]
        self._texts = [(text, 'Amatic-Bold', (0, 0, 0), 'center') for text in texts]


def test_preview_is_the_placeholder_until_a_picture_exists(cfg, templates_dir):
    choice = TemplateChoice(str(templates_dir / 'photomaton.xml'))

    assert Preview().build(choice, cfg) is choice.placeholder


def test_preview_assembles_the_last_capture_in_the_template(cfg, templates_dir, capture):
    choice = TemplateChoice(str(templates_dir / 'photomaton.xml'))
    preview = Preview()
    preview.expect()
    preview.store(FakeFactory(capture, ['Hello', '']), 0)

    image = preview.build(choice, cfg)

    assert not preview.waiting
    assert image.size == (1749, 1182)
    assert image.getpixel((873, 496))[:3] == CAPTURE_COLOR
    assert preview.build(choice, cfg) is image  # cached


def test_preview_of_a_broken_template_is_none(cfg, templates_dir, capture):
    choice = TemplateChoice(str(templates_dir / 'photomaton.xml'))
    choice.parser.data = {}  # No page for any capture number
    preview = Preview()
    preview.store(FakeFactory(capture, []), 0)

    assert preview.build(choice, cfg) is None


@pytest.mark.parametrize('start, end, step', [
    ((500, 200), (300, 210), 1),    # to the left: next
    ((300, 200), (500, 190), -1),   # to the right: previous
    ((300, 200), (330, 200), 0),    # too short
    ((300, 200), (400, 400), 0),    # mostly vertical
])
def test_swipe(start, end, step):
    swipe = Swipe()
    swipe.press(start)

    assert swipe.release(end, 1000) == step


def test_swipe_release_without_press_is_ignored():
    assert Swipe().release((0, 0), 1000) == 0


@pytest.fixture
def surface():
    pygame.font.init()
    return pygame.Surface((800, 480))


@pytest.fixture
def drawn_caption(cfg, templates_dir, surface):
    caption = Caption()
    caption.draw(surface, make_chooser(cfg, templates_dir))
    return caption


def test_caption_hit_test(drawn_caption):
    rect = drawn_caption.rect

    assert drawn_caption.step_for(drawn_caption.previous_rect.center) == -1
    assert drawn_caption.step_for(drawn_caption.next_rect.center) == 1
    assert drawn_caption.step_for(rect.center) == 0
    assert drawn_caption.step_for((rect.left, rect.bottom + 10)) is None


def test_caption_hit_test_before_drawing():
    assert Caption().step_for((10, 10)) is None


def mouse(event_type, pos):
    return types.SimpleNamespace(type=event_type, button=1, pos=pos)


def test_selection_step_consumes_arrow_keys(drawn_caption, surface):
    events = [types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_RIGHT),
              types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_p)]

    assert selection_step(drawn_caption, Swipe(), surface, events) == 1
    assert [event.key for event in events] == [pygame.K_p]


def test_selection_step_consumes_a_swipe(drawn_caption, surface):
    events = [mouse(pygame.MOUSEBUTTONDOWN, (600, 300)), mouse(pygame.MOUSEBUTTONUP, (200, 300))]

    assert selection_step(drawn_caption, Swipe(), surface, events) == 1
    assert events == [events[0]]


def test_selection_step_keeps_a_simple_tap(drawn_caption, surface):
    tap = mouse(pygame.MOUSEBUTTONUP, (600, 300))
    events = [mouse(pygame.MOUSEBUTTONDOWN, (600, 300)), tap]

    assert selection_step(drawn_caption, Swipe(), surface, events) == 0
    assert tap in events


def test_selection_step_follows_the_caption_arrows(drawn_caption, surface):
    pos = drawn_caption.previous_rect.center
    events = [mouse(pygame.MOUSEBUTTONDOWN, pos), mouse(pygame.MOUSEBUTTONUP, pos)]

    assert selection_step(drawn_caption, Swipe(), surface, events) == -1
