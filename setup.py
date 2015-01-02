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
        'redis'
    ],
    description='arkOS core system management libraries',
    author='CitizenWeb',
    author_email='jacob@citizenweb.io',
    url='http://arkos.io/',
    packages=["arkos"]
)
