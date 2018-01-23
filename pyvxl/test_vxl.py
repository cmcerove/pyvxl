#!/usr/bin/env python

import sys
import logging
from binascii import unhexlify
from pyvxl.transmit import Transmit


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
