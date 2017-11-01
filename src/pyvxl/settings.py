#!/usr/bin/env python

"""
Settings for pyvxl
"""

import os
import logging

__component__ = 'pyvxl'
__version__ = '00.01.000'
PROGRAM_VERSION = __component__ + '_' + __version__

# Debugging settings
DEFAULT_DEBUG_MESSAGE = "%(levelname)s: %(message)s"
if os.path.splitext(__file__)[1] == '.py':  # pragma: no cover
    VERBOSE_DEBUG_MESSAGE = "%(process)d-%(levelname)s: %(message)s (%(filename)s:%(lineno)d)"
else:  # pragma: no cover
    VERBOSE_DEBUG_MESSAGE = "%(filename)s:%(lineno)d-%(levelname)s: %(message)s"
DEFAULT_DEBUG_LEVEL = logging.INFO
VERBOSE_DEBUG_LEVEL = logging.DEBUG

# Workspace locations
SETTINGS_PATH = os.path.abspath(__file__)
README_PATH = os.path.normpath(os.path.join(os.path.dirname(SETTINGS_PATH), '..', '..',
                                            'release_artifacts', 'revisions.readme'))
ROOT = os.path.normpath(os.path.join(os.path.dirname(SETTINGS_PATH), '..', '..', '..', '..', '..'))
