#!/usr/bin/env python

"""Used for testing the daemon class."""

import logging
from time import sleep
from pyvxl.example_daemon import ExampleDaemon


def main():
    logging.basicConfig(level=logging.DEBUG)

    test_daemon = ExampleDaemon(logging=logging)
    test_daemon.print_task(1, 2, 4, period=5000, kwarg2=2)
    # test_daemon.print_task({'a': 'b'}, [], period=15000)
    # test_daemon.print_task(period=10000)
    sleep(5)

    test_daemon.__del__()


if __name__ == '__main__':
    main()
