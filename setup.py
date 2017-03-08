#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

long_description = (
    'This client library is designed to support the Facebook Graph API and the '
    'official Facebook JavaScript SDK, which is the canonical way to implement '
    'Facebook authentication.'
)

setup(
    name='facebook-python-sdk',
    version='0.2.1+eventbrite',
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
