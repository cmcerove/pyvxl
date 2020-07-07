#!/usr/bin/env python3

"""Unit tests for pyvxl.vxl."""
import pytest
import logging
import re
from pyvxl import VxlCan
from pyvxl.vxl import Vxl, VxlChannel, BUS_TYPE_CAN, BUS_TYPE_LIN
from pyvxl import vxl as vxl_file


@pytest.fixture
def vxl():
    """Test fixture for pyvxl.vxl.VxlCan."""
    vxl = VxlCan()
    vxl.start()
    return vxl


def test_init():  # noqa
    with pytest.raises(TypeError):
        VxlCan(channel='one')
    with pytest.raises(TypeError):
        VxlCan(baud='five hundred thousand')
    vxl = VxlCan(channel=None)
    assert vxl.channels == {}
    assert vxl.bus_type == BUS_TYPE_CAN


def test_open_port_fail(vxl, monkeypatch):  # noqa
    with pytest.raises(AssertionError):
        vxl.open_port('test')

    vxl.stop()
    def vxl_open_port_fail(one, two, three, four, five, six, seven):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_open_port', vxl_open_port_fail)
    with pytest.raises(AssertionError):
        vxl.open_port('test')

    channel = list(vxl.channels.keys())[0]
    vxl.remove_channel(channel)
    with pytest.raises(AssertionError):
        vxl.open_port('test')


def test_close_port_errors(vxl): # noqa
    vxl.close_port()
    with pytest.raises(AssertionError):
        vxl.close_port()


def test_bus_type_errors():  # noqa
    vxl = Vxl()
    with pytest.raises(NotImplementedError):
        vxl.bus_type = BUS_TYPE_LIN
    vxl.bus_type = BUS_TYPE_CAN
    with pytest.raises(AssertionError):
        vxl.bus_type = BUS_TYPE_CAN


def test_rx_queue_size_fails(vxl):  # noqa
    with pytest.raises(AssertionError):
        vxl.rx_queue_size = 32
    vxl.stop()
    with pytest.raises(TypeError):
        vxl.rx_queue_size = '32'
    with pytest.raises(ValueError):
        vxl.rx_queue_size = 8
    with pytest.raises(ValueError):
        vxl.rx_queue_size = 20


def test_add_channel_fails(vxl):  # noqa
    channel = list(vxl.channels.keys())[0]
    with pytest.raises(AssertionError):
        vxl.add_channel(channel, 500000)
    vxl.stop()
    with pytest.raises(ValueError):
        vxl.add_channel(channel, 500000)
    with pytest.raises(ValueError):
        vxl.add_channel(-1, 500000)


def test_remove_channel_fails(vxl):  # noqa
    with pytest.raises(AssertionError):
        vxl.remove_channel(-1)
    vxl.stop()
    with pytest.raises(ValueError):
        vxl.remove_channel(-1)


def test_receive_fail(vxl):  # noqa
    vxl.stop()
    with pytest.raises(AssertionError):
        vxl.receive()


def test_receive(vxl):  # noqa
    channel = list(vxl.channels.keys())[0]
    assert vxl.receive() is None
    assert vxl.send(channel, 0x123, '1234')
    msg_start_pat = re.compile(r'^(\w+)\sc=(\d+),\st=(\d+),\s')
    rx_tx_pat = re.compile(r'id=(\w+)\sl=(\d),\s(\w+)?\s(TX)?\s*tid=(\w+)')
    data = vxl.receive()
    print(data)
    matched = msg_start_pat.match(data)
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
    data = data.replace(matched.group(0), '')
    matched = rx_tx_pat.match(data)
    assert matched.group(1) == '0123'
    assert matched.group(2) == '2'
    assert matched.group(3) == '1234'
    assert matched.group(4) == 'TX'


def test_send_recv_extended(vxl):  # noqa
    channel = list(vxl.channels.keys())[0]
    assert vxl.receive() is None
    assert vxl.send(channel, 0x12345678, '1122334455667788')
    msg_start_pat = re.compile(r'^(\w+)\sc=(\d+),\st=(\d+),\s')
    rx_tx_pat = re.compile(r'id=(\w+)\sl=(\d),\s(\w+)?\s(TX)?\s*tid=(\w+)')
    data = vxl.receive()
    print(data)
    matched = msg_start_pat.match(data)
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
    data = data.replace(matched.group(0), '')
    matched = rx_tx_pat.match(data)
    assert matched.group(1) == '92345678'
    assert matched.group(2) == '8'
    assert matched.group(3) == '1122334455667788'
    assert matched.group(4) == 'TX'


def test_get_dll_version(vxl):  # noqa
    ver = vxl.config.dllVersion
    major = ((ver & 0xFF000000) >> 24)
    minor = ((ver & 0xFF0000) >> 16)
    build = ver & 0xFFFF
    assert f'{major}.{minor}.{build}' == vxl.get_dll_version()


def test_get_rx_queued_length(vxl):  # noqa
    assert isinstance(vxl.get_rx_queued_length(), int)


def test_get_time(vxl):  # noqa
    time = vxl.get_time()
    assert isinstance(time, int)
    assert time >= 0


def test_print_config(vxl):  # noqa
    # Nothing to verify really, just doing this for coverage
    vxl.print_config(debug=True)
    vxl.print_config()
    vxl.config.channelCount = 0
    vxl.print_config()


def test_channel_init_fail():  # noqa
    with pytest.raises(TypeError):
        VxlChannel('')


def test_channel_num_fail(vxl):  # noqa
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    with pytest.raises(AssertionError):
        channel.num = vxl.config.channelCount + 1

    with pytest.raises(AssertionError):
        channel_cfg = vxl.config.channel[vxl.config.channelCount - 1]
        channel_cfg.channelBusCapabilities = 0
        channel.num = 0


def test_channel_fails(vxl):  # noqa
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    with pytest.raises(TypeError):
        channel.init_access = 1
    with pytest.raises(AssertionError):
        channel.activate()
    vxl.stop()
    with pytest.raises(AssertionError):
        channel.activate()


def test_channel_bus_type_fail():  # noqa
    vxl = Vxl()
    with pytest.raises(AssertionError):
        VxlChannel(vxl)


def test_channel_baudrate_fail(vxl, monkeypatch):  # noqa
    vxl.stop()
    vxl.open_port('test')
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    channel.init_access = True
    def vxl_set_baudrate_fail(one, two, three):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_set_baudrate', vxl_set_baudrate_fail)
    with pytest.raises(AssertionError):
        channel.activate()


def test_channel_flush_tx_queue_fail(vxl, monkeypatch):  # noqa
    vxl.stop()
    vxl.open_port('test')
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    channel.init_access = True
    def vxl_set_baudrate_pass(one, two, three):  # noqa
        return True
    monkeypatch.setattr(vxl_file, 'vxl_set_baudrate', vxl_set_baudrate_pass)
    def vxl_flush_tx_queue_fail(one, two):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_flush_tx_queue',
                        vxl_flush_tx_queue_fail)
    with pytest.raises(AssertionError):
        channel.activate()


def test_channel_flush_rx_queue_fail(vxl, monkeypatch):  # noqa
    vxl.stop()
    vxl.open_port('test')
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    channel.init_access = True
    def vxl_set_baudrate_pass(one, two, three):  # noqa
        return True
    monkeypatch.setattr(vxl_file, 'vxl_set_baudrate', vxl_set_baudrate_pass)
    def vxl_flush_tx_queue_pass(one, two):  # noqa
        return True
    monkeypatch.setattr(vxl_file, 'vxl_flush_tx_queue',
                        vxl_flush_tx_queue_pass)
    def vxl_flush_rx_queue_fail(one):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_flush_rx_queue',
                        vxl_flush_rx_queue_fail)
    with pytest.raises(AssertionError):
        channel.activate()


def test_channel_activate_channel_fail(vxl, monkeypatch):  # noqa
    vxl.stop()
    vxl.open_port('test')
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    channel.init_access = False
    def vxl_activate_channel_fail(one, two, three, four):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_activate_channel',
                        vxl_activate_channel_fail)
    with pytest.raises(AssertionError):
        channel.activate()


def test_deactivate_fails(vxl, monkeypatch):  # noqa
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    vxl.close_port()
    with pytest.raises(AssertionError):
        channel.deactivate()
    vxl.open_port('test')
    channel.deactivate()
    with pytest.raises(AssertionError):
        channel.deactivate()
    channel.activate()
    def vxl_deactivate_channel_fail(one, two):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_deactivate_channel',
                        vxl_deactivate_channel_fail)
    with pytest.raises(AssertionError):
        channel.deactivate()


def test_request_chip_state(vxl):  # noqa
    vxl.request_chip_state()


def test_request_chip_state_fails(vxl, monkeypatch):  # noqa
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    def vxl_request_chip_state_fail(one, two):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_request_chip_state',
                        vxl_request_chip_state_fail)
    with pytest.raises(AssertionError):
        vxl.request_chip_state()
    channel.deactivate()
    with pytest.raises(AssertionError):
        vxl.request_chip_state()
    channel.activate()
    vxl.close_port()
    with pytest.raises(AssertionError):
        vxl.request_chip_state()


def test_start():  # noqa
    """."""
    vxl = VxlCan()
    assert vxl.started is False
    vxl.start()
    assert vxl.started is True


def test_stop_fail(vxl):  # noqa
    """."""
    vxl.stop()
    with pytest.raises(AssertionError):
        vxl.stop()


def test_flush_queues(vxl):  # noqa
    vxl.flush_queues()


def test_vxl_send_with_data_and_short_id(vxl):  # noqa
    channel = list(vxl.channels.keys())[0]
    assert vxl.send(channel, 0x123, '010203')


def test_vxl_send_without_data_and_long_id(vxl):  # noqa
    channel = list(vxl.channels.keys())[0]
    assert vxl.send(channel, 0x1234567, '')


def test_send_fail(vxl):  # noqa
    with pytest.raises(ValueError):
        vxl.send(-1, 123, '')


def test_get_can_channels(vxl):  # noqa
    if vxl.config.channelCount == 2:
        assert vxl.get_can_channels() == []
    else:
        # There is a CAN case connected but it's not guaranteed to have any
        # CAN channels so nothing to assert
        vxl.get_can_channels()

    if vxl.config.channelCount == 2:
        assert len(vxl.get_can_channels(include_virtual=True)) == 2
    else:
        assert len(vxl.get_can_channels(include_virtual=True)) >= 2
