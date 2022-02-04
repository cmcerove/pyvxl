#!/usr/bin/env python3

"""
Installer for pyvxl.

Run 'make.bat' to install.
"""

from sys import executable, argv, exit
from os import path, name, system
from time import time, sleep
from subprocess import call
from ctypes import WinDLL, windll
from platform import architecture
from setuptools import setup, find_packages


if name != 'nt':
    print('pyvxl is only supported in windows!')
    exit(1)


lib_path = path.normpath(path.join(path.dirname(__file__), 'lib'))

update_xl_path = path.join(lib_path, 'update_xl_lib.py')
exe_path = path.join(lib_path, 'Vector XL Driver Library Setup.exe')
ps_cmd = f"Start-Process -FilePath '{exe_path}' -ArgumentList '/S /v/qn' -Wait"
ps_cmd = f"powershell -command \"{ps_cmd}\""
version_file = path.join(lib_path, 'version.txt')


with open(version_file, 'r') as f:
    vxl_version = f.read()
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


def is_admin():  # noqa
    try:
        return windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


try:
    dll = WinDLL(vxl_path)
except WindowsError:
    if path.isfile(vxl_path):
        print(f'Failed importing {vxl_path}')
        exit(1)
    else:
        if not path.isfile(exe_path):
            call([executable, update_xl_path])
        if not path.isfile(exe_path):
            print(f'Something went wrong running {update_xl_path} to download '
                  f'{exe_path}. Either rerun this script to try again or run '
                  'update_xl_lip.py manually to download the file.')
            exit(1)
        if not is_admin():
            windll.shell32.ShellExecuteW(None, "runas", executable,
                                         ' '.join(argv), None, 1)
            # Wait 60s for the program to finish installing
            start = time()
            while (time() - start) < 60:
                sleep(1)
                if path.isfile(vxl_path):
                    break
            else:
                print(f'Failed installing {exe_path}. Try installing it '
                      'manually and then rerunning the batch file.')
                exit(1)
        else:
            print('Installing Vector XL Driver Library...')
            system(ps_cmd)
            if not path.isfile(vxl_path):
                print(f'Something went wrong installing {exe_path}')
                exit(1)
        try:
            dll = WinDLL(vxl_path)
        except WindowsError:
            print(f'Failed importing {vxl_path}')
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
