#!/usr/bin/env python

"""Configuration file for tests in this folder."""

from os import path, remove
from glob import glob


def pytest_sessionfinish(session, exitstatus):
    """Called after all tests have finished executing."""
    # Remove log files if all tests pass
    if not exitstatus:
        tests_dir = path.dirname(path.realpath(__file__))
        for log_file in glob(path.join(tests_dir, '*.asc')):
            remove(log_file)
    # with open('session_finish', 'w') as f:
    #     f.write('{} - {}'.format(time(), dir(session), exitstatus))
