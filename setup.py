#!/usr/bin/env python
"""
Setup module for core library.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from setuptools import setup, find_packages


setup(
    name='arkos-core',
    version='0.8.0',
    install_requires=[
        'ntplib',
        'passlib',
        'pyOpenSSL',
        'python-nginx',
        'dbus-python',
        'pycryptsetup',
        'pyparted',
        'python-ldap',
        'psutil',
        'netifaces',
        'GitPython',
        'python-gnupg',
        'python-pacman'
    ],
    description='arkOS core system management libraries',
    author='CitizenWeb',
    author_email='jacob@citizenweb.io',
    url='http://arkos.io/',
    packages=find_packages(),
    data_files=[
        ('/etc/arkos', ['defaults/settings.json']),
        ('/etc/arkos', ['defaults/policies.json']),
    ]
)
