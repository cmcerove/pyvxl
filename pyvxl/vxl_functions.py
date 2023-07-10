#!/usr/bin/env python

"""A common interface to vxlapi functions."""

import logging
from sys import exit
from os import path
from glob import glob
from platform import architecture
from ctypes import WinDLL, c_char_p


vxl_base_path = r'C:\Users\Public\Documents\Vector\XL Driver Library'
xl_libs = glob(f'{vxl_base_path}*')
arch, _ = architecture()
if xl_libs:
    # Grab the latest version
    vxl_lib_path = sorted(xl_libs)[-1]
    vxl_lib_path = path.join(vxl_lib_path, 'bin')
    if arch == '64bit':
        vxl_path = path.join(vxl_lib_path, 'vxlapi64.dll')
    else:
        vxl_path = path.join(vxl_lib_path, 'vxlapi.dll')
else:
    # These get installed with Vector drivers
    if arch == '64bit':
        vxl_path = path.join(r'C:\Windows\System32', 'vxlapi64.dll')
    else:
        vxl_path = path.join(r'C:\Windows\SysWOW64', 'vxlapi.dll')
        vxl_path = path.join(vxl_lib_path, 'vxlapi.dll')

if path.isfile(vxl_path):
    vxDLL = WinDLL(vxl_path)
else:
    print(f'ERROR: Unable to find {vxl_path}. '
          'Please install Vector\'s XL Driver Library and try again.')
    exit(1)


getError = vxDLL.xlGetErrorString
getError.restype = c_char_p
getEventStr = vxDLL.xlCanGetEventString
getEventStr.restype = c_char_p


def vxl_open_driver(*args):
    """Connect to the vxlAPI dll."""
    status = getError(vxDLL.xlOpenDriver(*args))
    logging.debug('{0}: {1}'.format('xLOpenDriver', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_close_driver(*args):
    """Disconnect from the vxlAPI dll."""
    status = getError(vxDLL.xlCloseDriver(*args))
    logging.debug('{0}: {1}'.format('xLCloseDriver', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_open_port(*args):
    """Open a port."""
    status = getError(vxDLL.xlOpenPort(*args))
    logging.debug('{0}: {1}'.format('xLOpenPort', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_close_port(*args):
    """Close a port."""
    status = getError(vxDLL.xlClosePort(*args))
    logging.debug('{0}: {1}'.format('xLClosePort', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_activate_channel(*args):
    """Activate a channel."""
    status = getError(vxDLL.xlActivateChannel(*args))
    logging.debug('{0}: {1}'.format('xlActivateChannel', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_deactivate_channel(*args):
    """Deactivate a channel."""
    status = getError(vxDLL.xlDeactivateChannel(*args))
    logging.debug('{0}: {1}'.format('xlDeactivateChannel', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_transmit(*args):
    """Transmit a CAN message."""
    status = getError(vxDLL.xlCanTransmitEx(*args))
    # logging.debug('{0}: {1}'.format('xlCanTransmitEx', status))
    return status


def vxl_receive(*args):
    """Receive a message."""
    status = getError(vxDLL.xlCanReceive(*args))
    # Since this causes so much spam during debugging, it should be uncommented
    # temporarily.
    # if status != 'XL_ERR_QUEUE_IS_EMPTY':
    #     logging.debug('{0}: {1}'.format('xlReceive', status))
    return True if status != b'XL_ERR_QUEUE_IS_EMPTY' else False


def vxl_get_receive_queue_size(*args):
    """Get the number of items in the receive queue."""
    status = getError(vxDLL.xlGetReceiveQueueLevel(*args))
    logging.debug('{0}: {1}'.format('xlGetReceiveQueueLevel', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_get_driver_config(*args):
    """Get the driver configuration."""
    status = getError(vxDLL.xlGetDriverConfig(*args))
    logging.debug('{0}: {1}'.format('xlGetDriverConfig', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_get_sync_time(*args):
    """Get the driver sync time in nanoseconds."""
    status = getError(vxDLL.xlGetSyncTime(*args))
    logging.debug('{0}: {1}'.format('xlGetSyncTime', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_get_event_str(*args):
    """Get a string description of an event."""
    return getEventStr(*args).decode('utf-8')


def vxl_set_baudrate(*args):
    """Set the baudrate."""
    status = getError(vxDLL.xlCanSetChannelBitrate(*args))
    logging.debug('{0}: {1}'.format('xlCanSetChannelBitrate', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_set_fd_conf(*args):
    """Set the CAN FD configuration."""
    status = getError(vxDLL.xlCanFdSetConfiguration(*args))
    logging.debug('{0}: {1}'.format('xlCanFdSetConfiguration', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_set_notification(*args):
    """Set a notification."""
    status = getError(vxDLL.xlSetNotification(*args))
    logging.debug('{0}: {1}'.format('xlSetNotification', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_set_transceiver(*args):
    """Set CAN related tranceiver settings."""
    status = getError(vxDLL.xlCanSetChannelTransceiver(*args))
    logging.debug('{0}: {1}'.format('xlCanSetChannelTransceiver', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_set_channel_output(*args):
    """Set CAN channel output to normal or silent."""
    status = getError(vxDLL.xlCanSetChannelOutput(*args))
    logging.debug('{0}: {1}'.format('xlCanSetChannelOutput', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_set_channel_mode(*args):
    """Set whether tx/txrq receipts for tx messages are enabled."""
    status = getError(vxDLL.xlCanSetChannelMode(*args))
    logging.debug('{0}: {1}'.format('xlCanSetChannelMode', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_request_chip_state(*args):
    """Request the CAN chip state be put in the receive queue."""
    status = getError(vxDLL.xlCanRequestChipState(*args))
    # Since this causes so much spam during debugging, it should be uncommented
    # temporarily.
    # logging.debug('{0}: {1}'.format('xlCanRequestChipState', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_flush_tx_queue(*args):
    """Flush the CAN transmit queue."""
    status = getError(vxDLL.xlCanFlushTransmitQueue(*args))
    logging.debug('{0}: {1}'.format('xlCanFlushTransmitQueue', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_flush_rx_queue(*args):
    """Flush the receive queue."""
    status = getError(vxDLL.xlFlushReceiveQueue(*args))
    logging.debug('{0}: {1}'.format('xlFlushReceiveQueue', status))
    return True if status == b'XL_SUCCESS' else False


def vxl_reset_clock(*args):
    """Reset the clock."""
    status = getError(vxDLL.xlResetClock(*args))
    logging.debug('{0}: {1}'.format('xlResetClock', status))
    return True if status == b'XL_SUCCESS' else False
