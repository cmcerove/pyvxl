#!/usr/bin/env python

"""Import structure for pyvxl."""

# Configure logging for this module the recommended way:
# https://docs.python.org/3.11/howto/logging.html#configuring-logging-for-a-library
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())

from pyvxl.can import CAN
from pyvxl.can_types import Database as CanDatabase
from pyvxl.vxl import VxlCan
