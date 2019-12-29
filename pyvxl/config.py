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
import configparser

# Configuration file locations
FILENAMES = (
'setup.cfg',
'.pyvxl',
)

# Search directories
DIRECTORIES = (
os.getcwd(),  # current working directory
os.path.expanduser("~"),  # user's home directory
os.path.dirname(__file__),  # src/pyvxl (or install path)
)

# setup.cfg sections to parse
SECTIONS = (
'pyvxl',
)

CAN_CHANNEL_1 = 2
CAN_BAUD_RATE_1 = 500000
DBC_PATH_1 = ''

CAN_CHANNEL_2 = 3
CAN_BAUD_RATE_2 = 500000
DBC_PATH_2 = ''

LIN_CHANNEL_1 = 1


def get(name):  # pylint: disable=W0621
    """Return the value of a configuration variable."""
    val = ''
    try:
        val = os.getenv(name)
    except AttributeError:
        pass
    return val


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
    os.environ[str(name)] = str(value)
    setattr(sys.modules[__name__], name, value)


# Populate the environment from configuration files
for directory in DIRECTORIES:
    for filename in FILENAMES:
        path = os.path.join(directory, filename)
        if os.path.isfile(path):
            config = configparser.RawConfigParser()
            config.read(path)
            for section in SECTIONS:
                if config.has_section(section):
                    for name, value in config.items(section):
                        if not get(name.upper()):
                            set(name.upper(), value, show=False)
                            setattr(sys.modules[__name__], name, get(name))


# Create global module variables for each environment variable
for name in list(globals().keys()):
    if name:
        for config_name in ['CAN', 'LIN', 'DBC']:
            if config_name in name:
                setattr(sys.modules[__name__], name, get(name))
                break
