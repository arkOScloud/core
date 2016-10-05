#!/usr/bin/env python
"""
Setup module for core library.

arkOS Core
(c) 2016 CitizenWeb
Written by Jacob Cook
Licensed under GPLv3, see LICENSE.md
"""

from setuptools import setup, find_packages

install_requires = [
    'cryptography',
    'free_tls_certificates',
    'GitPython',
    'gnupg',
    'miniupnpc',
    'netifaces',
    'ntplib',
    'pydbus',
    'pyldap',
    'pyparted==3.10.7',
    'pycryptsetup==1.7.2',
    'python-gnupg',
    'python-pacman',
    'python-nginx',
    'psutil',
    'requests',
    'semantic_version'
]

dependency_links = [
    'https://git.coderouge.co/arkOS/python-cryptsetup/repository/archive.tar.gz?ref=1.7.2#egg=pycryptsetup-1.7.2',
    'https://github.com/rhinstaller/pyparted/archive/v3.10.7.tar.gz#egg=pyparted-3.10.7'
]


setup(
    name='arkos-core',
    version='0.8.0',
    install_requires=install_requires,
    dependency_links=dependency_links,
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
