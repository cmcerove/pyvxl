#!/usr/bin/env python3

"""Unit tests for pyvxl.can_types."""

import pytest
from os import path
from pyvxl.can_types import Database, Node, Message, Signal


@pytest.fixture()
def db():
    """Test fixture for pyvxl.vector.CAN."""
    dbc_path = path.join(path.dirname(path.realpath(__file__)), 'test_dbc.dbc')
    return Database(dbc_path)


def test_dbc_import():  # noqa
    pass


def test_signals(db):  # noqa
    sig = db.get_signal('msg6_sig1')
    assert sig.val == 0
    assert sig.msg.data == ('00' * sig.msg.dlc)
    sig.val = 4206
    assert sig.num_val == 4206
    assert sig.val == 4206
    assert sig.raw_val == 0x6E10000000000000
    assert sig.msg.data == '6E10000000000000'
