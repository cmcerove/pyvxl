#!/usr/bin/env python

"""
Installer for pyvxl libraries and command-line tools.

Run "python setup.py install" to install script shortcuts in your path.

Requires setuptools (http://pypi.python.org/pypi/setuptools/).
"""

import os
import sys
import platform
import subprocess
import pkg_resources
if os.name == 'nt':
    from ctypes import WinDLL
from setuptools import setup, find_packages
import admin

LIB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), 'lib'))

missing_dependencies = []

#TODO: Uncomment this are once unit tests have been imported
'''
# Install 3rd-party libraries (Python sources)
for library_version in ('argparse-1.2.1',
                        'nose-1.2.1',
                        'unittest2-0.5.1'):
    library, version = library_version.rsplit('-', 1)
    try:
        if pkg_resources.get_distribution(library).version < version:
            raise pkg_resources.DistributionNotFound
    except pkg_resources.DistributionNotFound:
        install_package(library_version)
'''

# Install the vector dll
try:
    if os.name == 'nt':
        try:
            vxDLL = WinDLL("c:\\Users\\Public\\Documents\\Vector XL Driver Library\\bin\\vxlapi.dll")
        except WindowsError:
            vxDLL = WinDLL("c:\\Users\\Public\\Documents\\Vector XL Driver Library\\bin\\vxlapi64.dll")
            #vxDLL = WinDLL("c:\\Documents and Settings\\All Users\\Documents\\Vector XL Driver Library\\bin\\vxlapi.dll")
except WindowsError:
    if not admin.isUserAdmin():
        path = os.path.join(LIB_PATH, 'xl_lib97.exe')
        admin.runAsAdmin(cmdLine=[path])
        raw_input('Press return to continue . . .')
    else:
        print('Failed to aquire admin privileges necessary to install xl_lib97. Aborting...')
        sys.exit(1)


if os.name == 'nt':
    sys.path.append('C:\\Python27\\Lib\\site-packages\\win32')

# Install pyvxl
console_scripts = []  # pylint: disable=C0103
warnings = []  # pylint: disable=C0103
console_scripts.append("can = pyvxl:main")
#
# Create scripts
setup(

    name='pyvxl',
    version='0.1.1',

    description=("A python interface to the vector vxlapi.dll for CAN communication."),
    author="Chris Cerovec",
    author_email="chris.cerovec@gmail.com",

    packages=find_packages(),
    package_data={'pyvxl': ['*.dbc']},
    entry_points={'console_scripts': console_scripts},

    install_requires=["ply",
                      "colorama",
                      "configparser",
                      "pypiwin32"],

)

# Show warnings
if warnings:
    print('\n' + '\n'.join(warnings))
