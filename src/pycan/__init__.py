#!/usr/bin/env python

"""
Package for pycan.
"""

# Default interface
from pycan.common import __program__
from pycan.vector import Vector
from pycan.cmd_line import main
from pycan.can232 import CAN232, run
