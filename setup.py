#!/usr/bin/env python3

"""
Installer for pyvxl.

Run 'make.bat' to install.
"""

import sys
from os import path, name, system
from platform import architecture

if name != 'nt':
    print('pyvxl is only supported in windows!')
    sys.exit(1)

from ctypes import WinDLL
from setuptools import setup, find_packages

LIB_PATH = path.normpath(path.join(path.dirname(__file__), 'lib'))

arch, _ = architecture()
if arch == '64bit':
    vxl_path = ('c:\\Users\\Public\\Documents\\Vector XL Driver Library\\'
                'bin\\vxlapi64.dll')
else:
    vxl_path = ('c:\\Users\\Public\\Documents\\Vector XL Driver Library\\'
                'bin\\vxlapi.dll')

# TODO: Figure out how to check the installed version to decide if updating
#       is necessary.

try:
    dll = WinDLL(vxl_path)
except WindowsError:
    exe = r'.\lib\Vector XL Driver Library Setup.exe'
    ps_cmd = f"Start-Process -FilePath '{exe}' -ArgumentList '/S /v/qn' -Wait"
    system(f"powershell -command \"{ps_cmd}\"")
    try:
        dll = WinDLL(vxl_path)
    except WindowsError:
        print('Failed importing the dll. Exiting...')
        sys.exit(1)

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
