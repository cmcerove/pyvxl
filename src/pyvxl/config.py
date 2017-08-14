#!/usr/bin/env python

"""
loads configuration variables from the environment and configuration files.

The following files:

 - .pyvxl
 - setup.cfg

can be placed in the following locations:

 - <current working directory>
 - <home directory>
 - <directory of this file>

and have configuration variables in sections called:

 - pyvxl

"""

import os
import sys
import ConfigParser

import Tkinter as tk
import tkMessageBox
from tkFileDialog import askopenfilename, asksaveasfilename

CAN_DRIVER_ENV = 'CAN_DRIVER'
DBC_PATH_ENV = 'DBC_PATH'
CAN_BAUD_RATE_ENV = 'CAN_BAUD_RATE'
LIN_BAUD_RATE_ENV = 'LIN_BAUD_RATE'

# Configuration file locations
FILENAMES = (
'setup.cfg',
'.pyvxl',
)
DIRECTORIES = (
os.getcwd(),  # current working directory
os.path.expanduser("~"),  # user's home directory
os.path.dirname(__file__),  # src/pyvxl (or install path)
)
SECTIONS = (
'pyvxl',
)


def get(name, show_gui=False):  # pylint: disable=W0621
    """Return the value of a configuration variable."""
    if show_gui:
        env_val = os.getenv(name)
        if not env_val:
            pass

    return os.getenv(name)


def get_with_reason(name):  # pylint: disable=W0621
    """Return the value of a configuration variable and a skip message for testing.

    Typical usage:

        @unittest.skipUnless(*config.get_with_reason(<variable>))
        class TestSomething(unittest.TestCase):
           ...
    """
    return get(name), "'{0}' is not defined".format(name)


def set(name, value, show=True):  # pylint: disable=W0621,W0622
    """Set the value of a configuration variable for the current environment."""
    if show and get(name) != value:
        sys.stdout.write("{0} = {1}\n".format(name, value))
    os.environ[name] = str(value)
    setattr(sys.modules[__name__], name, value)


# Populate the environment from configuration files
for directory in DIRECTORIES:
    for filename in FILENAMES:
        path = os.path.join(directory, filename)
        if os.path.isfile(path):
            config = ConfigParser.RawConfigParser()
            config.read(path)
            for section in SECTIONS:
                if config.has_section(section):
                    for name, value in config.items(section):
                        if not(get(name.upper())):
                            set(name.upper(), value, show=False)


# Create global module variables for each environment variable
for name in list(globals().keys()):
    if name.endswith('_ENV'):
        setattr(sys.modules[__name__], name.rsplit('_ENV', 1)[0], get(name))
