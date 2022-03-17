#!/usr/bin/env python

"""Unit tests for pyvxl.vxl."""
import pytest
from time import sleep
from random import random
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
        vxl.rx_queue_size = 8200


def test_add_channel_fails(vxl):  # noqa
    channel = list(vxl.channels.keys())[0]
    with pytest.raises(AssertionError):
        # Adding a channel when the port is open
        vxl.add_channel()
    vxl.stop()
    with pytest.raises(ValueError):
        # Adding a channel that was already added
        vxl.add_channel(num=channel)
    with pytest.raises(ValueError):
        # Adding a channel with an invalid number
        vxl.add_channel(num=-1)


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
    XL_CAN_EV_TAG_RX_OK = 0x0400  # noqa
    XL_CAN_EV_TAG_RX_ERROR = 0x0401  # noqa
    XL_CAN_EV_TAG_TX_ERROR = 0x0402  # noqa
    XL_CAN_EV_TAG_TX_REQUEST = 0x0403  # noqa
    XL_CAN_EV_TAG_TX_OK = 0x0404  # noqa
    XL_CAN_EV_TAG_CHIP_STATE = 0x0409  # noqa

    XL_CAN_TXMSG_FLAG_EDL = 0x0001  # noqa
    XL_CAN_TXMSG_FLAG_BRS = 0x0002  # noqa
    fd_flags = XL_CAN_TXMSG_FLAG_EDL | XL_CAN_TXMSG_FLAG_BRS

    # Test all valid message lengths for regular and extended IDs
    ids_to_test = [0x123, 0x12345678]
    valid_dlcs = list(range(9)) + [12, 16, 20, 24, 32, 48, 64]
    for msg_id in ids_to_test:
        for dlc in valid_dlcs:
            # Generate random data to send
            tx_data = ''.join([f'{int(random()*0xFF):02X}' for x in range(dlc)])
            vxl.flush_queues()
            assert vxl.receive() is None
            assert vxl.send(channel, msg_id, tx_data)
            sleep(0.01)
            rx_event = vxl.receive()
            assert rx_event is not None
            assert rx_event.tag == XL_CAN_EV_TAG_TX_OK
            assert isinstance(rx_event.timeStampSync / 1000000000.0, float)
            assert rx_event.channelIndex + 1 == channel
            assert (rx_event.tagData.canRxOkMsg.canId & 0x7FFFFFFF) == msg_id
            dlc_map = {9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64}
            if dlc <= 8:
                assert rx_event.tagData.canRxOkMsg.msgFlags == 0
                assert rx_event.tagData.canRxOkMsg.dlc == dlc
            else:
                assert dlc_map[rx_event.tagData.canRxOkMsg.dlc] == dlc
                assert rx_event.tagData.canRxOkMsg.msgFlags == fd_flags
            rx_data = rx_event.tagData.canRxOkMsg.data
            data = ''.join([f'{x:02X}' for i, x in enumerate(rx_data) if i < dlc])
            assert data == tx_data


def test_get_rx_queued_length(vxl):  # noqa
    length = vxl.get_rx_queued_length()
    assert isinstance(length, int)
    assert isinstance(length, bool) is False


def test_get_rx_queued_length_no_port():  # noqa
    vxl = Vxl()
    with pytest.raises(AssertionError):
        vxl.get_rx_queued_length()


def test_reset_clock(vxl):  # noqa
    vxl.reset_clock()


def test_reset_clock_no_port():  # noqa
    vxl = Vxl()
    with pytest.raises(AssertionError):
        vxl.reset_clock()


def test_get_dll_version(vxl):  # noqa
    ver = vxl.config.dllVersion
    major = ((ver & 0xFF000000) >> 24)
    minor = ((ver & 0xFF0000) >> 16)
    build = ver & 0xFFFF
    assert f'{major}.{minor}.{build}' == vxl.get_dll_version()


def test_get_time(vxl):  # noqa
    time = vxl.get_time()
    assert isinstance(time, int)
    assert isinstance(time, bool) is False
    assert time >= 0


def test_print_config(vxl):  # noqa
    # Nothing to verify really, just doing this for coverage
    vxl.print_config(debug=True)
    vxl.print_config()
    vxl.config.channelCount = 0
    vxl.print_config()


def test_channel_invalid_types(vxl):  # noqa
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    with pytest.raises(TypeError):
        VxlChannel('')
    with pytest.raises(TypeError):
        channel.num = False
    with pytest.raises(TypeError):
        channel.init_access = 1
    with pytest.raises(TypeError):
        channel.baud = False
    with pytest.raises(TypeError):
        channel.sjw_arb = False
    with pytest.raises(TypeError):
        channel.tseg1_arb = False
    with pytest.raises(TypeError):
        channel.tseg2_arb = False
    with pytest.raises(TypeError):
        channel.data_baud = False
    with pytest.raises(TypeError):
        channel.sjw_data = False
    with pytest.raises(TypeError):
        channel.tseg1_data = False
    with pytest.raises(TypeError):
        channel.tseg2_data = False


def test_channel_num_fails(vxl):  # noqa
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    with pytest.raises(AssertionError):
        channel.num = vxl.config.channelCount + 1

    with pytest.raises(AssertionError):
        channel_cfg = vxl.config.channel[vxl.config.channelCount - 1]
        channel_cfg.channelBusCapabilities = 0
        channel.num = 0


def test_channel_activate_fails(vxl):  # noqa
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    with pytest.raises(AssertionError):
        channel.activate()
    vxl.stop()
    with pytest.raises(AssertionError):
        channel.activate()


def test_channel_bus_type_fail():  # noqa
    vxl = Vxl()
    with pytest.raises(AssertionError):
        VxlChannel(vxl)


def test_channel_fd_conf_fail(vxl, monkeypatch):  # noqa
    vxl.stop()
    vxl.open_port('test')
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    channel.init_access = True
    def vxl_set_fd_conf_fail(one, two, three):  # noqa
        return False
    monkeypatch.setattr(vxl_file, 'vxl_set_fd_conf', vxl_set_fd_conf_fail)
    with pytest.raises(AssertionError):
        channel.activate()


def test_channel_flush_tx_queue_fail(vxl, monkeypatch):  # noqa
    vxl.stop()
    vxl.open_port('test')
    channel = vxl.channels[list(vxl.channels.keys())[0]]
    channel.init_access = True
    def vxl_set_fd_conf_pass(one, two, three):  # noqa
        return True
    monkeypatch.setattr(vxl_file, 'vxl_set_fd_conf', vxl_set_fd_conf_pass)
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
    def vxl_set_fd_conf_pass(one, two, three):  # noqa
        return True
    monkeypatch.setattr(vxl_file, 'vxl_set_fd_conf', vxl_set_fd_conf_pass)
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


def test_channel_deactivate_fails(vxl, monkeypatch):  # noqa
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


def test_VxlCan_init():  # noqa
    vxl = VxlCan(rx_queue_size=8192)
    assert vxl.rx_queue_size == 8192


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
        # Invalid Channel
        vxl.send(-1, 123, '')
    channel = list(vxl.channels.keys())[0]
    dlc_map = {12: 9, 16: 10, 20: 11, 24: 12, 32: 13, 48: 14, 64: 15}
    for dlc in range(66):
        # Skip valid dlcs
        if dlc <= 8 or dlc in dlc_map:
            continue
        with pytest.raises(ValueError):
            # Invalid DLC
            vxl.send(channel, 0x123, '00' * dlc)


def test_send_queue_full(vxl, monkeypatch):  # noqa
    def vxl_queue_full(one, two, three, four, five, svar=[False]):  # noqa
        if not svar[0]:
            svar[0] = True
            return b'XL_ERR_QUEUE_IS_FULL'
        return b'XL_SUCCESS'
    monkeypatch.setattr(vxl_file, 'vxl_transmit', vxl_queue_full)

    channel = list(vxl.channels.keys())[0]
    assert vxl.send(channel, 0x123, '010203') is True


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
