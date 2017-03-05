#!/usr/bin/env python

"""
Installer for CPP_AUTOTEST libraries and command-line tools.

Run "python setup.py develop" to install script shortcuts in your path.

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


# Install PyDAQmx
try:
    import PyDAQmx
except NotImplementedError:
    install_package('PyDAQmx-1.2.5.2')
    print "National Instruments NIDAQ driver not found!"
    print "Please download and install them from: "
    print "http://www.ni.com/download/ni-daqmx-14.0/4918/en/"
except ImportError:
    install_package('PyDAQmx-1.2.5.2')


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

# Install autotest
console_scripts = []  # pylint: disable=C0103
warnings = []  # pylint: disable=C0103
from autotest import mock_gui
console_scripts.append(mock_gui.__program__ + " = autotest.mock_gui:main")
from autotest import mock_gui_mmui
console_scripts.append(mock_gui_mmui.__program__ + " = autotest.mock_gui_mmui:main")
from autotest import mock_gui_dbapi
console_scripts.append(mock_gui_dbapi.__program__ + " = autotest.mock_gui_dbapi:main")
from autotest import mock_gui_appsdk
console_scripts.append(mock_gui_appsdk.__program__ + " = autotest.mock_gui_appsdk:main")
from autotest import ihu
console_scripts.append(ihu.__program__ + " = autotest.ihu:main")
from autotest import reporting_auto
console_scripts.append(reporting_auto.__program__ + " = autotest.reporting_auto:main")
from autotest import reporting_unit
console_scripts.append(reporting_unit.__program__ + " = autotest.reporting_unit:main")
from autotest import mock_user
console_scripts.append(mock_user.__program__ + " = autotest.mock_user:main")
try:
    from autotest import mock_dbus_server
    from autotest import mock_dbus_client
except Exception as exception:  # pylint: disable=W0703,C0103
    warnings.append("WARNING: {0}".format(exception))
else:
    console_scripts.append(mock_dbus_server.__program__ + " = autotest.mock_dbus_server:main")
    console_scripts.append(mock_dbus_client.__program__ + " = autotest.mock_dbus_client:main")
try:
    from autotest import introspection
except Exception as exception:  # pylint: disable=W0703,C0103
    warnings.append("WARNING: {0}".format(exception))
else:
    console_scripts.append(introspection.__program__ + " = autotest.introspection:main")
from autotest import relays
console_scripts.append(relays.__program__ + " = autotest.relays:main")
from autotest.relays import remote_server
console_scripts.append(remote_server.__program__ + " = autotest.relays.remote_server:main")
from autotest.relays import remote_client
console_scripts.append(remote_client.__program__ + " = autotest.relays.remote_client:main")
from autotest import sci
console_scripts.append(sci.__program__ + " = autotest.sci:main")
from autotest import can
console_scripts.append(can.__program__ + " = autotest.can:main")
from autotest import daq
console_scripts.append(daq.__program__ + " = autotest.daq:main")
from autotest import lin
#
# Create scripts
from autotest import settings
setup(

name='autotest',
version=settings.__version__,

description=("Framework for remotely testing an IHU with mocked components."),
author="Jace Browning",
author_email="jace.browning@jci.com",

packages=find_packages(),
package_data={'autotest': ['*.cfg', '*.xsl'],
              'autotest.can': ['*.dbc']},

entry_points={'console_scripts': console_scripts},
)

# Show warnings
if warnings:
    print '\n' + '\n'.join(warnings)
