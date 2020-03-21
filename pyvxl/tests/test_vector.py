#!/usr/bin/env python

"""Unit tests for pyvxl.vector."""

import pytest
import logging
from pyvxl import CAN
from pyvxl import vector


@pytest.fixture
def can():
    """Test fixture for pyvxl.vector.CAN."""
    can = CAN(db_path='test_dbc.dbc')
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
    assert can.imported is True
    with pytest.raises(TypeError):
        can.import_db(1234)
    with pytest.raises(ValueError):
        can.import_db('1234')
    with pytest.raises(ValueError):
        can.db_path = None
        can.import_db()
    with pytest.raises(AttributeError):
        can.import_db('test_vector.py')
