#!/usr/bin/env python

"""
Installer for pyvxl.

Run 'make.bat' to install.
"""

from os import name
from setuptools import setup, find_packages


if name != 'nt':
    print('pyvxl is only supported in windows!')
    exit(1)


setup(

    name='pyvxl',
    version='0.2.0',

    description=('A python interface to the vector vxlapi.dll.'),
    author='Chris Cerovec',
    author_email='chris.cerovec@gmail.com',

    packages=find_packages(),
    package_data={'pyvxl': ['*.dbc']},
    entry_points={'console_scripts': 'can = pyvxl:main'},

    install_requires=['ply',
                      'pytest',
                      'colorama',
                      'coverage',
                      'configparser',
                      'beautifulsoup4'],

    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows :: Windows 10',
    ],
    python_requires='>=3.8'
)
