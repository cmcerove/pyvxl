#!/usr/bin/env python

"""Unit tests for pyvxl.vxl."""
import pytest
import logging
import re
from pyvxl import VxlCan
from pyvxl import vxl as vxl_file

CAN_SUPPORTED = 0x10000
CAN_BUS_TYPE = 1


@pytest.fixture
def vxl():
    """Test fixture for pyvxl.vxl.VxlCan."""
    vxl = VxlCan()
    vxl.start()
    return vxl


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


def test_start_invalid_channel(caplog):
    """."""
    vxl = VxlCan()
    expected = 'Unable to start with an invalid channel!'
    vxl.channel_valid = False
    assert vxl.start() is False
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_start_open_port_fail(caplog, monkeypatch):
    """."""
    vxl = VxlCan()
    def vxl_open_port_fail(one, two, three, four, five, six, seven):
        return False
    monkeypatch.setattr(vxl_file, 'vxl_open_port', vxl_open_port_fail)
    expected = 'Failed to open the port!'
    assert vxl.start() is False
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_start_active_channel_fail(caplog, monkeypatch):
    """."""
    vxl = VxlCan()
    def vxl_activate_channel_fail(one, two, three, four):
        return False
    monkeypatch.setattr(vxl_file, 'vxl_activate_channel',
                        vxl_activate_channel_fail)
    expected = 'Failed to activate the channel'
    assert vxl.start() is False
    assert caplog.record_tuples == [('root', logging.ERROR, expected)]


def test_start_valid(caplog):
    """."""
    vxl = VxlCan()
    caplog.set_level(logging.INFO)
    channel = vxl.driver_config.channelCount
    expected = ('Successfully connected to Channel {} @ {}Bd!'
                ''.format(channel, 500000))
    assert vxl.start()
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


def test_reconnect(vxl, monkeypatch):
    """."""
    # # Flush tx queue doesn't work with virtual CAN channels so it needs to be
    # # mocked.
    # def vxl_flush_override(*args):
    #     pass
    # monkeypatch.setattr(vxl_file, 'vxl_flush_tx_queue', vxl_flush_override)
    vxl.reconnect()


def test_vxl_send_with_data_and_short_id(vxl, caplog):
    """."""
    caplog.set_level(logging.DEBUG)
    assert vxl.send(0x123, '010203')


def test_vxl_send_without_data_and_long_id(vxl, caplog):
    """."""
    caplog.set_level(logging.DEBUG)
    assert vxl.send(0x1234567, '')


def test_receive(vxl):
    """."""
    assert vxl.receive() is None
    assert vxl.send(0x123, '1234')
    pat = re.compile('^(\w+)\sc=(\d+),\st=(\d+),\sid=(\w+)\sl=(\d),\s(\w+)\s(TX)*\s*tid=(\w+)')
    data = vxl.receive()
    matched = pat.match(data)
    assert matched
    assert matched.group(1) == 'RX_MSG'
    # Channel might change, just check that it exists
    channel = matched.group(2)
    assert channel
    assert int(channel)
    # Timestamp will change, check that it exists
    time = matched.group(3)
    assert time
    assert int(time)
    assert matched.group(4) == '0123'
    assert matched.group(5) == '2'
    assert matched.group(6) == '1234'
    assert matched.group(7) == 'TX'


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


def test_get_rx_queue_size(vxl):
    """."""
    assert isinstance(vxl.get_rx_queue_size(), int)


def test_request_ship_state(vxl):
    """."""
    vxl.request_chip_state()


def test_get_time(vxl):
    """."""
    time = vxl.get_time()
    # TODO: will fail in python 3 since long doesn't exist
    assert isinstance(time, long)
    assert time >= 0
