#!/usr/bin/env python3

"""
Installer for pyvxl.

Run 'make.bat' to install.
"""

import os
import sys

if os.name == 'nt':
    from ctypes import WinDLL
from setuptools import setup, find_packages
import admin

LIB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), 'lib'))
DLL_PATH = ('c:\\Users\\Public\\Documents\\Vector XL Driver Library\\bin\\'
            'vxlapi.dll')

try:
    if os.name == 'nt':
        vxDLL = WinDLL(DLL_PATH)
except WindowsError:
    # Install the vxlAPI.dll
    if not admin.isUserAdmin():
        path = os.path.join(LIB_PATH, 'xl_lib97.exe')
        admin.runAsAdmin(cmdLine=[path])
        input('Press return to continue . . .')
    else:
        print('Failed to aquire admin privileges necessary to install '
              'xl_lib97. Aborting...')
        sys.exit(1)


if os.name == 'nt':
    sys.path.append('C:\\Python27\\Lib\\site-packages\\win32')

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
                      'configparser',
                      'pypiwin32',
                      'beautifulsoup4'],

    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Environment :: Win32 (MS Windows)',
        'Operating System :: Microsoft :: Windows :: Windows 10',
    ],
    python_requires='>=3.8'
)
