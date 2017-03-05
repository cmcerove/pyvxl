#!/usr/bin/env python

"""
Settings for CPP_AUTOTEST.
"""

import os
import logging

__component__ = 'CPP_AUTOTEST'
__version__ = '00.47.000'
PROGRAM_VERSION = __component__ + '_' + __version__

# IHU settings
STARTUP_DELAY = 20  # seconds to wait for processes to start
MAX_PING_ATTEMPTS = 10  # maximum number of times to ping a target while waiting for it to appear

# GUI settings
MESSAGE_LOG_TIMEOUT = 2  # number of seconds to retrieve all logged message

# D-Bus settings
DAEMON_REFRESH_DELAY = 2  # number of seconds to wait for refresh after stopping a process
MESSAGE_LOG_TIMEOUT = 3  # number of seconds to timeout when receiving all logged messages
CALL_LOG_TIMEOUT = 2  # number of seconds for timeout when receiving all logged method calls
SIGNAL_LOG_TIMEOUT = 4  # number of seconds for timeout when receiving all logged signals
SUBPROCESS_DELAY = 10  # number of seconds to wait for a D-Bus subprocess to start

# Browser settings
BROWSER_START_DELAY = 10  # number of seconds to wait for browser to launch
BROWSER_REFRESH_DELAY = 8  # number of seconds to wait for the home screen to load after a refresh
BROWSER_KEY_DELAY = 1  # number of seconds between unique keystrokes in a sequence
BROWSER_KEY_DELAY_MIN = .4  # minimum number of seconds required between consecutive keystrokes

# Debugging settings
DEFAULT_DEBUG_MESSAGE = "%(levelname)s: %(message)s"
if os.path.splitext(__file__)[1] == '.py':  # pragma: no cover
    VERBOSE_DEBUG_MESSAGE = "%(process)d-%(levelname)s: %(message)s (%(filename)s:%(lineno)d)"
else:  # pragma: no cover
    VERBOSE_DEBUG_MESSAGE = "%(process)d-%(levelname)s: %(message)s"
DEFAULT_DEBUG_LEVEL = logging.INFO
VERBOSE_DEBUG_LEVEL = logging.DEBUG

# Workspace locations
SETTINGS_PATH = os.path.abspath(__file__)
README_PATH = os.path.normpath(os.path.join(os.path.dirname(SETTINGS_PATH), '..', '..',
                                            'release_artifacts', 'revisions.readme'))
ROOT = os.path.normpath(os.path.join(os.path.dirname(SETTINGS_PATH), '..', '..', '..', '..', '..'))
