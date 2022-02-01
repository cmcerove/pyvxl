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

lib_path = path.normpath(path.join(path.dirname(__file__), 'lib'))

exe_path = path.join(lib_path, 'Vector XL Driver Library Setup.exe')
ps_cmd = f"Start-Process -FilePath '{exe_path}' -ArgumentList '/S /v/qn' -Wait"
ps_cmd = f"powershell -command \"{ps_cmd}\""


vxl_version = '11.6.12'
vxl_base_path = r'C:\Users\Public\Documents\Vector\XL Driver Library '
vxl_lib_path = f'{vxl_base_path}{vxl_version}'
vxl_lib_path = path.join(vxl_lib_path, 'bin')

# The current version isn't installed. Install it.
if not path.isdir(vxl_lib_path):
    system(ps_cmd)

arch, _ = architecture()
if arch == '64bit':
    vxl_path = path.join(vxl_lib_path, 'vxlapi64.dll')
else:
    vxl_path = path.join(vxl_lib_path, 'vxlapi.dll')

try:
    dll = WinDLL(vxl_path)
except WindowsError:
    if path.isfile(vxl_path):
        print(f'Failed importing {vxl_path}')
        sys.exit(1)
    else:
        system(ps_cmd)
        if not path.isfile(vxl_path):
            print(f'Something went wrong installing {exe_path}')
            sys.exit(1)
        try:
            dll = WinDLL(vxl_path)
        except WindowsError:
            print(f'Failed importing {vxl_path}')
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
