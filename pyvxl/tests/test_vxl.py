#!/usr/bin/env python

"""Tests for pyvxl.vxl.

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
from pyvxl import VxlCan
from pyvxl import vxl as vxl_file

CAN_SUPPORTED = 0x10000
CAN_BUS_TYPE = 1


@pytest.fixture
def vxl():
    """Test fixture for pyvxl.CAN."""
    return VxlCan()


def test_invalid_channel_type():
    """."""
    with pytest.raises(TypeError):
        VxlCan(channel='one')


def test_invalid_baud_rate_type():
    """."""
    with pytest.raises(TypeError):
        VxlCan(baud_rate='five hundred thousand')


def test_set_channel_no_channels(vxl, caplog):
    """."""
    vxl.driver_config.channelCount = False
    vxl.set_channel(1)
    assert caplog.record_tuples == [('root', logging.ERROR,
                                     'No available CAN channels!')]


def test_set_channel_invalid_channel(vxl, caplog):
    """."""
    channel = vxl.driver_config.channelCount + 1
    expected = 'Channel {} does not exist!'.format(channel)
    vxl.set_channel(channel)
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_set_channel_no_can_support(vxl, caplog):
    """."""
    channel = vxl.driver_config.channelCount
    channel_config = vxl.driver_config.channel[channel - 1]
    channel_config.channelBusCapabilities = ~CAN_SUPPORTED
    expected = 'Channel {} doesn\'t support CAN!'.format(channel)
    vxl.set_channel(channel)
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_start_invalid_channel(vxl, caplog):
    """."""
    expected = 'Unable to start with an invalid channel!'
    vxl.channel_valid = False
    assert vxl.start() is False
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_start_open_port_fail(vxl, caplog, monkeypatch):
    """."""
    def vxl_open_port_fail(one, two, three, four, five, six, seven):
        return False
    monkeypatch.setattr(vxl_file, 'vxl_open_port', vxl_open_port_fail)
    expected = 'Failed to open the port!'
    assert vxl.start() is False
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_start_active_channel_fail(vxl, caplog, monkeypatch):
    """."""
    def vxl_activate_channel_fail(one, two, three, four):
        return False
    monkeypatch.setattr(vxl_file, 'vxl_activate_channel',
                        vxl_activate_channel_fail)
    expected = 'Failed to activate the channel'
    assert vxl.start() is False
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_start_valid(vxl, caplog):
    """."""
    caplog.set_level(logging.INFO)
    channel = vxl.driver_config.channelCount
    expected = ('Successfully connected to Channel {} @ {}Bd!'
                ''.format(channel, 500000))
    assert vxl.start() is True
    assert caplog.record_tuples == [('root', logging.INFO, expected)]


def test_stop_channel_activated_port_opened(vxl):
    """."""
    vxl.channel_activated = True
    vxl.port_opened = True
    vxl.stop()
    assert vxl.channel_activated is False
    assert vxl.port_opened is False


def test_stop_channel_deactivated_port_closed(vxl):
    """."""
    vxl.channel_activated = False
    vxl.port_opened = False
    vxl.stop()
    assert vxl.channel_activated is False
    assert vxl.port_opened is False


def test_reconnect_fail_virtual_channel(vxl):
    """."""
    with pytest.raises(ValueError):
        vxl.reconnect()


def test_reconnect(vxl, monkeypatch):
    """."""
    # Flush tx queue doesn't work with virtual CAN channels so it needs to be
    # mocked.
    def vxl_flush_override(*args):
        pass
    monkeypatch.setattr(vxl_file, 'vxl_flush_tx_queue', vxl_flush_override)
    vxl.reconnect()


def test_high_voltage_wakeup_error(vxl):
    """."""
    with pytest.raises(NotImplementedError):
        vxl.high_voltage_wakeup()


def test_vxl_send_with_data_and_short_id(vxl, caplog):
    """."""
    caplog.set_level(logging.DEBUG)
    assert vxl.start() is True
    assert vxl.send(0x123, '010203') is True


def test_vxl_send_without_data_and_long_id(vxl, caplog):
    """."""
    assert vxl.start() is True
    caplog.set_level(logging.DEBUG)
    assert vxl.send(0x1234567, '') is True


def test_receive(vxl):
    """."""
    assert vxl.start() is True
    assert vxl.receive() is None
    assert vxl.send(0x123, '1234') is True
    rx, ch, ts, mid, dlc, data, tx, tid = vxl.receive()
    assert rx == 'RX_MSG'
    assert mid == 'id=0123'
    assert dlc == 'l=2,'
    assert data == '1234'
    assert tx == 'TX'


def test_get_can_channels(vxl):
    """."""
    if vxl.driver_config.channelCount == 2:
        assert vxl.get_can_channels() == []
    else:
        # There is a CAN case connected but it's not guaranteed to have any
        # CAN channels so nothing to assert
        vxl.get_can_channels()

    if vxl.driver_config.channelCount == 2:
        assert len(vxl.get_can_channels(include_virtual=True)) == 2
    else:
        assert len(vxl.get_can_channels(include_virtual=True)) >= 2


def test_print_config(vxl):
    """."""
    # Nothing to verify really, just doing this for coverage
    vxl.print_config(debug=True)
    vxl.print_config()
    vxl.driver_config.channelCount = 0
    vxl.print_config()
