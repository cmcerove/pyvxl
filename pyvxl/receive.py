#!/usr/bin/env python

"""pyvxl's receive process."""

import logging
from select import select
from socket import socket, AF_INET, SOCK_STREAM
from pysib.daemon import Daemon

logging.basicConfig(level=logging.INFO)


class Receive(Daemon):
    """."""
