#!/usr/bin/env python

from distutils.core import setup

setup(
    name='arkos',
    version='0.7',
    install_requires=[
        'ntplib',
        'passlib',
        'pyOpenSSL',
        'python-iptables',
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
    packages=["arkos"],
    data_files=[
        ('/etc/arkos', ['defaults/settings.json']),
        ('/etc/arkos', ['defaults/policies.json']),
        ('/etc/arkos', ['defaults/secrets.json'])
    ]
)
