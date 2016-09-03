#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, setuptools

setup(
    name='videocutter',
    version='1.0.0',
    url='https://github.com/ozmartian/videocutter',
    license='GPL2',
    author='Pete Alexandrou',
    author_email='pete@ozmartians.com',
    description='All-in-one video cutter and joiner built in PyQt5',
    packages=setuptools.find_packages(),
    install_requires=['PyQt5>=5.6']
)
