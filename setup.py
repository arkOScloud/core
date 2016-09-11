#!/usr/bin/env python
"""
Setup module for core library.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from setuptools import setup, find_packages

ir = [
    'cryptography',
    'ntplib',
    'python-nginx',
    'dbus-python',
    'pyparted',
    'pyldap',
    'psutil',
    'miniupnpc',
    'netifaces',
    'GitPython',
    'python-gnupg',
    'python-pacman'
]


setup(
    name='arkos-core',
    version='0.8.0',
    install_requires=[],
    description='arkOS core system management libraries',
    author='CitizenWeb',
    author_email='jacob@citizenweb.io',
    url='http://arkos.io/',
    packages=find_packages(),
    test_suite='tests',
    data_files=[
        ('/etc/arkos', ['defaults/settings.json']),
        ('/etc/arkos', ['defaults/policies.json']),
    ]
)
