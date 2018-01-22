#!/usr/bin/env python

import logging
from time import sleep
from binascii import unhexlify
from pyvxl.transmit import Transmit


def main():
    logging.basicConfig(level=logging.DEBUG)
    transmit = Transmit()

    transmit.add(0x301, unhexlify("01020304"), 1000)

    raw_input('press enter to exit')

    transmit.__del__()


if __name__ == '__main__':
    main()
