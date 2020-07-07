#!/usr/bin/env python3

"""Unit tests for pyvxl.vector.

Possible command line options for pytest:
    --junitxml=report.xml
        xml result output that should be readable by teamcity. There are
        additional test fixture that can be used to add more information to
        the xml report:
            record_property
            record_xml_attribute
            record_testsuite_property
    -q
        quiet mode
    -k
        keyword expression (case insensitive) e.g. "MyClass and not method"
    -m
        marker expressions e.g. -m slow will run tests decorated with
        @pytest.mark.slow
    -x
        stop after the first failure
    --maxfail=2
        stop after 2 failures

pystest file_name::function_name
    tests only function_name within file_name
pystest file_name::TestClass::function_name
    tests only function_name within TestClass within file_name

Other pytest notes:
    with pytest.raises(Exception) to test for an exception

    def test_func(tmpdir) will create a temporary directory
"""
import pytest
import logging
from time import sleep
from os import path
from pyvxl import CAN, VxlCan


# Possible keyword arguments for @pytest.fixture:
#   scope
#       Possible values: 'function'(default), 'class', 'module', 'session' or
#                         'package'(experimental)
#       The scope for which the fixture is shared. This parameter may also be
#       a callable which receives (fixture_name, config) as parameters and
#       must return a str with one of the values mentioned above. More can
#       be found in the Dynamic scope section of the pytest docs.
#   params
#       An optional list of parameters which will cause multiple invocations
#       of the fixture function and all of the tests using it. The current
#       parameter is available in request.param.
#   autouse
#       If True, the fixture func is activated for all tests that can see it.
#       if False (the default), then an explicit reference is needed to
#       activate the fixture.
#   ids
#       List of string ids each corresponding to the params so that they are
#       part of the test id. If no ids are provided, they will be generated
#       automatically from the params.
#   name=Defaults to the name of the decorated function.
#       The name of the fixture. This defaults to the name of the decorated
#       function. If a fixture is used in the same module in which it is
#       defined, the function name of the fixture will be shadowed by the
#       function arg that requests the fixture; one way to resolve this is to
#       name the decorated function fixture_<fixturename> and then use
#       @pytest.fixture(name='<fixturename>')
@pytest.fixture(scope='module')
def can():
    """Test fixture for pyvxl.vector.CAN."""
    dbc_path = path.join(path.dirname(path.realpath(__file__)), 'test_dbc.dbc')
    can = CAN()
    can.add_channel(db=dbc_path)
    return can


def test_logging(can):
    """."""
    can1 = list(can.channels.values())[0]
    name = 'test_log'
    opened = can.start_logging(name, False)
    # Give the receive thread time to start logging
    sleep(0.1)
    assert (name + '.asc') == path.basename(opened)
    assert opened.endswith('.asc')
    assert path.isfile(opened)
    can1.send_message('msg3')
    # Give the receive thread time to receive it
    sleep(0.3)
    closed = can.stop_logging()
    sleep(0.3)
    assert opened == closed
    msg = can1.db.get_message('msg3')
    assert msg is not None
    # Send a message and check that it's in the file
    with open(opened, 'r') as f:
        assert ' {:X} '.format(msg.id) in f.read()

def test_add_remove_channel(can):  # noqa
    current_channel = list(can.channels.keys())[0]
    with pytest.raises(ValueError):
        can.add_channel(current_channel)
    all_can_channels = VxlCan().get_can_channels(True)
    for channel in all_can_channels:
        if channel not in can.channels:
            with pytest.raises(ValueError):
                can.remove_channel(channel)
            added_channel = can.add_channel(channel)
            removed_channel = can.remove_channel(added_channel.num)
            assert added_channel == removed_channel
        else:
            can.remove_channel(channel)
    assert can.channels == {}
    with pytest.raises(TypeError):
        can.remove_channel('fake_channel')
    # Add the original channel back to prevent breaking other tests that use
    # can and expect at least one channel
    dbc_path = path.join(path.dirname(path.realpath(__file__)), 'test_dbc.dbc')
    orig_channel = can.add_channel(db=dbc_path)

    with pytest.raises(TypeError):
        orig_channel.db = 'one'


def test_sending_and_stopping_messages(can):  # noqa
    channel = list(can.channels.values())[0]
    msg1 = channel.db.get_message('msg1')
    assert msg1.sending is False
    assert msg1.period != 0
    msg2 = channel.db.get_message('msg2')
    assert msg2.sending is False
    assert msg2.period != 0
    msg3 = channel.db.get_message('msg3')
    assert msg3.sending is False
    assert msg3.period == 0

    msg1comp = channel.send_message('msg1')
    assert msg1 is msg1comp
    assert msg1.sending is True
    msg2comp = channel.send_message('msg2')
    assert msg2 is msg2comp
    assert msg2.sending is True
    msg3comp = channel.send_message('msg3')
    assert msg3 is msg3comp
    assert msg3.sending is False

    channel.stop_message('msg1')
    assert msg1.sending is False

    can.stop_all_messages()
    assert msg2.sending is False


def test_sending_and_stopping_signals(can):  # noqa
    channel = list(can.channels.values())[0]