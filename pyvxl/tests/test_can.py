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
import re
from time import sleep, perf_counter
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
    # The default is to connect to the last channel which is virtual
    # and always present.
    can.add_channel(db=dbc_path)
    return can


def test_logging(can):
    """."""
    msg_pat = re.compile(r'^\s*(\d+\.\d+)\s+(\d+)\s+([\dA-F]+)\s+([RT]x)'
                         r'\s+d\s*(\d+)((\s+[\dA-F][\dA-F])+).*')
    can1 = list(can.channels.values())[0]
    # The last 2 channels are virtual and can1.channel is set to the default
    # which is the last virtual channel
    can.add_channel(can1.channel - 1)
    # The second to last channel which is virtual
    name = 'test_can_log'
    opened = can.start_logging(name, False)
    # Give the receive thread time to start logging
    sleep(0.3)
    assert (name + '.asc') == path.basename(opened)
    assert opened.endswith('.asc')
    assert path.isfile(opened)
    msg3_sig1 = can1.db.get_signal('msg3_sig1')
    msg3_sig1.val = 1
    msg3_data = msg3_sig1.msg.data
    msg3 = can1.send_message('msg3')
    assert msg3 is msg3_sig1.msg
    assert msg3.id == 0x456
    assert msg3.dlc == 8
    assert msg3.data == msg3_data
    assert msg3.name == 'msg3'
    # Give the receive thread time to receive it
    sleep(0.3)
    closed = can.stop_logging()
    sleep(0.3)
    assert opened == closed
    # Check that both messages are in the file
    rx_found = False
    tx_found = False
    with open(opened, 'r') as f:
        for line in f:
            match = msg_pat.match(line)
            if match is not None:
                match = match.groups()
                channel = int(match[1])
                msg_id = int(match[2], 16)
                txrx = match[3]
                dlc = int(match[4])
                data = ''.join(match[5]).replace(' ', '')
                if msg_id == msg3.id:
                    if channel == can1.channel:
                        assert txrx == 'Tx'
                        tx_found = True
                        assert can1.channel == channel
                    else:
                        assert txrx == 'Rx'
                        rx_found = True
                        assert (can1.channel - 1) == channel
                    assert msg3.data == data
                    assert msg3.dlc == dlc

                if rx_found and tx_found:
                    break
        else:
            if rx_found:
                raise AssertionError(f'Tx for {msg3.id:X} not in the log')
            elif tx_found:
                raise AssertionError(f'Rx for {msg3.id:X} not in the log')
            else:
                raise AssertionError(f'Tx and Rx for {msg3.id:X} were not '
                                     'found in the log')

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
            removed_channel = can.remove_channel(added_channel.channel)
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

    msg4 = channel.send_new_message(0xABC, '12345', 200, 'msg4')
    assert msg4.id == 0xABC
    assert msg4.data == '012345'
    assert msg4.period == 200
    assert msg4.name == 'msg4'
    assert msg4.sending is True

    with pytest.raises(ValueError):
        channel.send_new_message(msg4.id)

    with pytest.raises(TypeError):
        channel.send_new_message(0x55555, None)

    channel.stop_message('msg1')
    assert msg1.sending is False

    can.stop_all_messages()
    assert msg2.sending is False


def test_sending_and_stopping_signals(can):  # noqa
    channel = list(can.channels.values())[0]


def test_queuing(can):  # noqa
    can2 = list(can.channels.values())[0]
    can.start_logging('queue_test')
    can2.start_queue('msg3')
    can2.send_message('msg3')
    start = perf_counter()
    # Make sure it doesn't pick up the message we just transmitted
    time, msg_data = can2.dequeue_msg('msg3', timeout=200)
    # assert 0.145 < (perf_counter() - start) < 0.355
    assert time is None
    assert msg_data is None
    can2.stop_queue('msg3')
    # The last 2 channels are virtual and can2.channel is set to the default
    # which is the last virtual channel
    can1 = can.add_channel(can2.channel - 1, db='test_dbc.dbc')
    # msg3 is not periodic. Test that exactly one message is received
    msg3_sig1 = can1.db.get_signal('msg3_sig1')
    msg3_sig1.value = 1
    assert msg3_sig1.value == 1
    msg3_data = msg3_sig1.msg.data
    assert msg3_data == '0000000000000001'
    can2.start_queue('msg3')
    can1.send_message('msg3')
    start = perf_counter()
    # Make sure it doesn't pick up the message we just transmitted
    time, msg_data = can2.dequeue_msg('msg3', timeout=200)
    # assert (perf_counter() - start) < 0.100
    assert time > 0
    assert isinstance(time, float)
    assert msg_data == msg3_data
    can.stop_logging()
