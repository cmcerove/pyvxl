#!/usr/bin/env python

"""Configuration file for tests in this folder.

pytest API reference: https://docs.pytest.org/en/latest/reference.html
    hooks: https://docs.pytest.org/en/latest/reference.html#hooks
"""

from os import path, remove
from time import sleep
from glob import glob


def pytest_sessionfinish(session, exitstatus):
    """Called after all tests have finished executing."""
    # Remove log files if all tests pass
    if not exitstatus:
        tests_dir = path.dirname(path.realpath(__file__))
        for log_file in glob(path.join(tests_dir, '*.asc')):
            for tries in range(5):
                try:
                    remove(log_file)
                except PermissionError:
                    sleep(1)
                else:
                    break
    # with open('session_finish', 'w') as f:
    #     f.write('{} - {}'.format(time(), dir(session), exitstatus))


'''
pytest_collection_modifyitems(session, config, items):
    """Called after collection has been performed.

    May filter or re-order the items in-place.

    Parameters:
        session (_pytest.main.Session) - the pytest session object
        config (_pytest.config.Config) - pytest config object
        items (List[_pytest.nodes.Item]) - list of item objects
    """
'''
