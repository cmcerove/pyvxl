#!/usr/bin/env python

import sys
import logging
import os
from time import sleep
from binascii import unhexlify
from pyvxl.transmit import Transmit
from nose import main, SkipTest
from nose.tools import timed
from pyvxl import CAN


class TestVectorCAN:
    """."""

    @classmethod
    def setup_class(cls):
        cls.can = CAN(0, 'CAN_3_Cluster.dbc')


    def test_logging(self):
        """Verify that logging can be started and stopped."""
        log_path = cls.can.start_logging('test_log')
        sleep()

    def test_find_message(self):
        """."""

    def test_find_signal(self):
        """."""

    def test_get_message(self):
        """."""

    def test_get_signals(self):
        """."""

    def test_wait_for_error(self):
        """."""

    def test_find_message(self):
        """."""

    def test_find_message(self):
        """."""

    def test_find_message(self):
        """."""

    def test_find_message(self):
        """."""
def main():
    logging.basicConfig(level=logging.DEBUG)
    transmit = Transmit()

    if len(sys.argv) == 1:
        transmit.add(0x301, unhexlify("01020304"), 1000)
    else:
        transmit.add(0x150, unhexlify("4321"), 1000)

    raw_input('press enter to exit')

    transmit.__del__()


if __name__ == '__main__':
    main()
