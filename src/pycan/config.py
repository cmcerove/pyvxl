#!/usr/bin/env python

"""
loads configuration variables from the environment and configuration files.

The following files:

 - .autotest
 - setup.cfg

can be placed in the following locations:

 - <current working directory>
 - <home directory>
 - <directory of this file>

and have configuration variables in sections called:

 - autotest
 - CPP_AUTOTEST

"""

import os
import sys
import ConfigParser

import Tkinter as tk
import tkMessageBox
from tkFileDialog import askopenfilename, asksaveasfilename

# Testing configuration variables
TARGET_ENV = 'TEST_IHU'  # specifies IP/hostname of networked IHU
DELAY_ENV = 'TEST_DELAY'  # specifies number of seconds for simulated user delay during testing
PHONESIM_ENV = 'TEST_PHONESIM'  # specifies address:port of a running phone simulator
BROWSER_ENV = 'TEST_BROWSER'  # specifies the path of a web browser to use for simulated user input
MANUAL_ENV = 'TEST_MANUAL'  # allows manual unit tests to run

# Hardware configuration variables
PORT_RELAYS_ENV = 'PORT_RELAYS'  # serial port of a connected relay box
NUM_RELAY_BOXES_ENV = 'NUM_RELAY_BOXES' #number of relay boxes
TYPE_RELAYS_ENV = 'TYPE_RELAYS'  # type of relays: 'SAINSMART', 'GBLITE' (default)
PORT_SCI_ENV = 'PORT_SCI'  # serial port of the SCI connection (for the MAP)
PORT_SCI_MAP_ENV = 'PORT_SCI_MAP'  # serial port of the MAP's SCI connection
PORT_SCI_VIP_ENV = 'PORT_SCI_VIP'  # serial port of the VIP's SCI connection
PORT_CAN_ENV = 'PORT_CAN'  # serial port or channel of connected CAN hardware
PORT_LIN_ENV = 'PORT_LIN' # channel of connected LIN hardware

CAN_DRIVER_ENV = 'CAN_DRIVER'
DBC_PATH_ENV = 'DBC_PATH'
CAN_BAUD_RATE_ENV = 'CAN_BAUD_RATE'
LIN_BAUD_RATE_ENV = 'LIN_BAUD_RATE'

# Configuration file locations
FILENAMES = (
'setup.cfg',
'.autotest',
)
DIRECTORIES = (
os.getcwd(),  # current working directory
os.path.expanduser("~"),  # user's home directory
os.path.dirname(__file__),  # src/cpp/autotest/src/autotest (or install path)
)
SECTIONS = (
'autotest',
'CPP_AUTOTEST'
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
