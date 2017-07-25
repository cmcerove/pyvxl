#!/usr/bin/env python

"""
Common interface to all CAN hardware.
"""

__program__ = 'can'

class BaseCAN(object):  # pragma: no cover, pylint: disable=R0921
    """Common interface to all CAN drivers."""

    def __init__(self, port, dbc_path, baud_rate):
        self.port = port
        self.dbc_path = dbc_path
        self.baud_rate = baud_rate

    def start(self, baudrate=None):
        """Open the port and start the driver.
        """
        raise NotImplementedError()

    def terminate(self):
        """Close the port and stop the driver.
        """
        raise NotImplementedError()

    def import_dbc(self):
        """Import a CAN database file"""
        raise NotImplementedError()

class Frame(object):  # pragma: no cover
    """Helper class to represents CAN data frames."""

    def __init__(self, fill='x'):
        self.fill = fill
        self.data = []

    def __str__(self):
        raise NotImplementedError()

    def set(self, start, size, value):
        """Set a range of bits."""
        raise NotImplementedError()

