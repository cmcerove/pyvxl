#!/usr/bin/env python

"""A common interface to vxlapi functions."""

import os
import logging
from ctypes import WinDLL, c_char_p

# Import the vector DLL
vxl_path = ("c:\\Users\\Public\\Documents\\Vector XL Driver Library\\"
            "bin\\vxlapi.dll")
if os.name == 'nt':
    if os.path.isfile(vxl_path):
        vxDLL = WinDLL(vxl_path)
    else:
        print('ERROR: Unable to find {}'.format(vxl_path))


getError = vxDLL.xlGetErrorString
getError.restype = c_char_p
getEventStr = vxDLL.xlGetEventString
getEventStr.restype = c_char_p


def vxl_open_driver(*args):
    """Connect to the vxlAPI dll."""
    status = getError(vxDLL.xlOpenDriver(*args))
    logging.debug("{0}: {1}".format("xLOpenDriver", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_close_driver(*args):
    """Disconnect from the vxlAPI dll."""
    status = getError(vxDLL.xlCloseDriver(*args))
    logging.debug("{0}: {1}".format("xLCloseDriver", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_open_port(*args):
    """."""
    status = getError(vxDLL.xlOpenPort(*args))
    logging.debug("{0}: {1}".format("xLOpenPort", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_close_port(*args):
    """."""
    status = getError(vxDLL.xlClosePort(*args))
    logging.debug("{0}: {1}".format("xLClosePort", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_activate_channel(*args):
    """."""
    status = getError(vxDLL.xlActivateChannel(*args))
    logging.debug("{0}: {1}".format("xlActivateChannel", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_deactivate_channel(*args):
    """."""
    status = getError(vxDLL.xlDeactivateChannel(*args))
    logging.debug("{0}: {1}".format("xlDeactivateChannel", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_transmit(*args):
    """."""
    status = getError(vxDLL.xlCanTransmit(*args))
    logging.debug("{0}: {1}".format("xlCanTransmit", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_receive(*args):
    """."""
    status = getError(vxDLL.xlReceive(*args))
    if status != 'XL_ERR_QUEUE_IS_EMPTY':
        logging.debug("{0}: {1}".format("xlReceive", status))
    return True if status != 'XL_ERR_QUEUE_IS_EMPTY' else False


def vxl_get_driver_config(*args):
    """."""
    status = getError(vxDLL.xlGetDriverConfig(*args))
    logging.debug("{0}: {1}".format("xlGetDriverConfig", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_get_event_str(*args):
    """."""
    return getEventStr(*args)


def vxl_set_baudrate(*args):
    """."""
    status = getError(vxDLL.xlCanSetChannelBitrate(*args))
    logging.debug("{0}: {1}".format("xlCanSetChannelBitrate", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_set_notification(*args):
    """."""
    status = getError(vxDLL.xlSetNotification(*args))
    logging.debug("{0}: {1}".format("xlSetNotification", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_set_transceiver(*args):
    """."""
    status = getError(vxDLL.xlCanSetChannelTransceiver(*args))
    logging.debug("{0}: {1}".format("xlCanSetChannelTransceiver", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_flush_tx_queue(*args):
    """."""
    status = getError(vxDLL.xlCanFlushTransmitQueue(*args))
    logging.debug("{0}: {1}".format("xlCanFlushTransmitQueue", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_flush_rx_queue(*args):
    """."""
    status = getError(vxDLL.xlFlushReceiveQueue(*args))
    logging.debug("{0}: {1}".format("xlFlushReceiveQueue", status))
    return True if status == 'XL_SUCCESS' else False


def vxl_reset_clock(*args):
    """."""
    status = getError(vxDLL.xlResetClock(*args))
    logging.debug("{0}: {1}".format("xlResetClock", status))
    return True if status == 'XL_SUCCESS' else False
