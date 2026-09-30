# -*- coding: utf-8 -*-

import os.path as osp
import shutil

import pytest
from PIL import Image

import pibooth_template_chooser
from pibooth.config.parser import PiConfigParser

DATA_DIR = osp.join(osp.dirname(__file__), 'data')
CAPTURE_COLOR = (200, 30, 40)


class FakePluginManager(object):

    def get_friendly_name(self, plugin, version=True):
        return plugin.__name__


def pytest_configure(config):
    # The options are declared in a module-level dictionary: once per session
    dummy = PiConfigParser('unused.cfg', FakePluginManager(), load=False)
    pibooth_template_chooser.pibooth_configure(dummy)


@pytest.fixture
def templates_dir(tmp_path):
    """A directory of two templates, one with a style file."""
    for name in ('photomaton', 'second'):
        shutil.copy(osp.join(DATA_DIR, 'photomaton.xml'), str(tmp_path / (name + '.xml')))
    (tmp_path / 'fonts').mkdir()
    (tmp_path / 'fonts' / 'Title.ttf').write_bytes(b'')
    (tmp_path / 'photomaton.cfg').write_text(
        "[TEMPLATE]\n"
        "name = Photomaton\n"
        "text_colors = ((0, 0, 0), (90, 90, 90))\n"
        "text_fonts = ('fonts/Title.ttf', 'Amatic-Bold')\n", encoding='utf-8')
    return tmp_path


@pytest.fixture
def cfg(tmp_path, templates_dir):
    config = PiConfigParser(str(tmp_path / 'pibooth.cfg'), FakePluginManager(), load=False)
    config.set('TEMPLATE_CHOOSER', 'directory', str(templates_dir))
    return config


@pytest.fixture
def capture():
    return Image.new('RGB', (1500, 1000), CAPTURE_COLOR)
