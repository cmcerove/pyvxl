#!/usr/bin/env python

"""Unit tests for pyvxl.vector."""

import pytest
import logging
from os import path
from pyvxl import CAN
from pyvxl import vector


@pytest.fixture
def can():
    """Test fixture for pyvxl.vector.CAN."""
    dbc_path = path.join(path.dirname(path.realpath(__file__)), 'test_dbc.dbc')
    can = CAN(db_path=dbc_path)
    can.import_db()
    return can


def test_start_logging():
    """."""
    pass


def test_stop_logging():
    """."""
    pass


def test_import_db(can):
    """."""
    can.import_db()
    with pytest.raises(TypeError):
        can.import_db(1234)
    with pytest.raises(ValueError):
        can.import_db('1234')
    with pytest.raises(ValueError):
        can.db_path = None
        can.import_db()
    with pytest.raises(ValueError):
        can.import_db('test_vector.py')
