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


def apt_get(package):
    """
    Installs an Ubuntu package using apt-get.
    """
    if os.name == 'nt':
        return False
    else:
        return subprocess.call(['sudo', 'apt-get', 'install',
                                package, '--yes', '--force-yes']) == 0


def install_deb(filename):
    """
    Installs Ubuntu package from filename in library folder.
    """
    if platform.linux_distribution()[-1] == 'lucid':
        return subprocess.call(['sudo', 'gdebi',
                                os.path.join(LIB_PATH, filename),
                                '--non-interactive']) == 0
    else:
        return False


def install_package(folder):  # pragma: no cover
    """
    Installs the Python package contained in the specified library folder path.
    """
    cwd = os.getcwd()
    path = os.path.join(LIB_PATH, folder)
    os.chdir(path)
    success = subprocess.call([sys.executable, 'setup.py', 'install']) == 0
    os.chdir(cwd)
    sys.path.append(path)
    return success


def install_exe(filename):  # pragma: no cover
    """
    Installs a Python package for Windows using an installer.
    """
    if os.name == 'nt':
        path = os.path.join(LIB_PATH, filename)
        result = (subprocess.call(path) == 0)
        print 'Installing '+filename
        raw_input('Press return when finished . . .')
        return result
    else:
        return False


# Install 3rd-party libraries (apt-get or local .deb packages)
try:
    import libxslt  # pylint: disable=F0401,W0611
except ImportError:
    apt_get('python-libxslt1')
try:
    import Tkinter  # pylint: disable=F0401,W0611
except ImportError:
    apt_get('python-tk')


# Install 3rd-party libraries (Python sources)
for library_version in ('argparse-1.2.1',
                        'coverage-3.5.2',
                        'ordereddict-1.1',
                        'nose-1.2.1',
                        'pyserial-2.6',
                        'unittest2-0.5.1',
                        'websocket-client-0.8.0',
                        'mock-1.0.1'):
    library, version = library_version.rsplit('-', 1)
    try:
        if pkg_resources.get_distribution(library).version < version:
            raise pkg_resources.DistributionNotFound
    except pkg_resources.DistributionNotFound:
        install_package(library_version)
try:
    import xlwt  # pylint: disable=W0611
except ImportError:
    install_package('xlwt-0.7.4')


# Install autopy
try:
    import autopy  # pylint: disable=F0401,W0611
except ImportError:
    if os.name == 'nt':
        install_exe('autopy-0.51.win32-py2.7.exe')
    else:
        apt_get('python-dev')
        apt_get('libx11-dev')
        apt_get('libxtst-dev')
        apt_get('python-dev')
        # Try to install a specific libpng version required by the 32-bit VMs
        if not install_deb('libpng12-dev_1.2.42-1ubuntu2.5_i386.deb'):
            apt_get('libpng12-dev')
        install_package('autopy-0.51')

# Install epydoc
try:
    import epydoc  # pylint: disable=F0401,W0611
except ImportError:
    if os.name == 'nt':
        install_exe('epydoc-3.0.1.win32.exe')
    else:
        install_package('epydoc-3.0.1')

# Install PyUSB (d2xx) for Windows or PyUSB (generic usb library) for Linux
if os.name == 'nt':
    try:
        import d2xx  # pylint: disable=F0401,W0611
    except ImportError:
        install_exe('PyUSB-1.6.win32-py2.7.exe')
else:
    try:
        import pylibftdi  # pylint: disable=F0401,W0611
    except ImportError:
        install_package('pylibftdi-0.12')
    try:
        import usb  # pylint: disable=F0401,W0611
    except ImportError:
        install_package('pyusb-1.0.0a3')

# Install pywin32
try:
    import win32com
except ImportError:
    if os.name == 'nt':
        install_exe('pywin32-218.win32-py2.7.exe')

# Install the vector dll
try:
    if os.name == 'nt':
        try:
            vxDLL = WinDLL("c:\\Users\\Public\\Documents\\Vector XL Driver Library\\bin\\vxlapi.dll")
        except WindowsError:
            vxDLL = WinDLL("c:\\Documents and Settings\\All Users\\Documents\\Vector XL Driver Library\\bin\\vxlapi.dll")
except WindowsError:
    if not admin.isUserAdmin():
        path = os.path.join(LIB_PATH, 'xl_lib83.exe')
        admin.runAsAdmin(cmdLine=[path])
        raw_input('Press return to continue . . .')
    else:
        install_exe('xl_lib83.exe')

# Install numpy
try:
    import numpy
except ImportError:
    try:
        install_exe('numpy-1.8.1-win32-superpack-python2.7.exe')
    except WindowsError:
        if not admin.isUserAdmin():
            path = os.path.join(LIB_PATH, 'numpy-1.8.1-win32-superpack-python2.7.exe')
            admin.runAsAdmin(cmdLine=[path])
            raw_input('Press return to continue . . .')

# Install colorama
try:
    import colorama
except ImportError:
    install_package('colorama-0.2.7')

# Install ply
try:
    import ply
except ImportError:
    install_package('ply-3.4')

if os.name == 'nt':
    sys.path.append('C:\\Python27\\Lib\\site-packages\\win32')

# Install pyvxl
console_scripts = []  # pylint: disable=C0103
warnings = []  # pylint: disable=C0103
from pyvxl import __program__
console_scripts.append(__program__ + " = pyvxl.can:main")
#
# Create scripts
setup(

name='pyvxl',
version=1.0,

description=("A python interface to the vector vxlapi.dll for CAN communication."),
author="Chris Cerovec",
author_email="chris.cerovec@gmail.com",

packages=find_packages(),
package_data={'pyvxl': ['*.dbc']},

entry_points={'console_scripts': console_scripts},
)

# Show warnings
if warnings:
    print '\n' + '\n'.join(warnings)
