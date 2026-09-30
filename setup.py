#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name='pibooth_template_chooser',
    version='2.0.0',
    description="Pibooth plugin letting guests choose the picture template on the wait screen",
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author="Ceeeeb",
    url="https://github.com/ceeeeb/pibooth-template-chooser",
    license='GPLv3',
    platforms=['unix', 'linux'],
    keywords=['Raspberry Pi', 'photobooth', 'pibooth', 'template'],
    packages=['pibooth_template_chooser'],
    package_data={'pibooth_template_chooser': ['templates/*.xml', 'templates/*.cfg', 'fonts/*']},
    # specname: several implementations of the same hook in the plugin
    install_requires=['pibooth-ceeeeb>=2.0.10', 'pluggy>=1.1'],
    zip_safe=False,
    entry_points={'pibooth': ["pibooth_template_chooser = pibooth_template_chooser"]},
)
