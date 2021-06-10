#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import
import codecs
import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with codecs.open(
    os.path.join(os.path.dirname(__file__), 'facebook', 'version.txt'),
    mode='rb',
    encoding='utf8',
) as _version_file:
    __version__ = _version_file.read().strip()

long_description = (
    'This client library is designed to support the Facebook Graph API and the '
    'official Facebook JavaScript SDK, which is the canonical way to implement '
    'Facebook authentication.'
)

setup(
    name='facebook-python-sdk',
    version=__version__,
    description='Eventbrite Fork of Facebook Python SDK',
    long_description=long_description,
    author='Facebook',
    url='http://github.com/eventbrite/facebook-python-sdk',
    package_dir={'facebook': 'facebook'},
    install_requires=[
        'requests>=2.4',
    ],
    packages=[
        'facebook',
    ],
)
