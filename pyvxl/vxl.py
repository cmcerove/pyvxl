#!/usr/bin/env python

"""Holds classes designed to interact specific protocols of vxlAPI."""

from pyvxl.vxl_c_functions import vxl_open_driver, vxl_close_driver
from pyvxl.vxl_c_functions import vxl_open_port, vxl_close_port
from pyvxl.vxl_c_functions import vxl_activate_channel, vxl_deactivate_channel
from pyvxl.vxl_c_functions import vxl_reset_clock, vxl_get_driver_config
from pyvxl.vxl_c_functions import vxl_transmit, vxl_receive
from pyvxl.vxl_c_functions import vxl_get_receive_queue_size
from pyvxl.vxl_c_functions import vxl_set_baudrate, vxl_get_sync_time
from pyvxl.vxl_c_functions import vxl_get_event_str, vxl_request_chip_state
from pyvxl.vxl_c_functions import vxl_flush_tx_queue, vxl_flush_rx_queue
from pyvxl.vxl_c_types import vxl_driver_config_type, vxl_event_type

import os
import logging
from ctypes import cdll, c_uint, c_int, c_ubyte, c_ulong, cast
from ctypes import c_ushort, c_ulonglong, pointer, sizeof, POINTER
from ctypes import c_long, create_string_buffer

# Grab the c library and some functions from it
if os.name == 'nt':
    libc = cdll.msvcrt
printf = libc.printf
strncpy = libc.strncpy
memset = libc.memset
memcpy = libc.memcpy

TRANSCEIVER_LINEMODE_NORMAL = 0x0009
TRANSCEIVER_TYPE_CAN_1051_CAP_FIX = 0x013C
OUTPUT_MODE_SILENT = 0
OUTPUT_MODE_NORMAL = 1

CAN_SUPPORTED = 0x10000
CAN_BUS_TYPE = 1


class VxlCan(object):
    """."""

    def __init__(self, channel=0, baud_rate=500000, rx_queue_size=8192):
        """."""
        if not isinstance(channel, int):
            raise TypeError('Expected int but got {}'.format(type(channel)))
        if not isinstance(baud_rate, int):
            raise TypeError('Expected int but got {}'.format(type(baud_rate)))
        self.port_opened = False
        self.channel_activated = False
        self.channel_valid = False
        self.port_handle = c_long(-1)
        self.driver_config = None
        # The hardware channel (starts at 1)
        self.channel = 0
        # channel_index = channel - 1; starts at 0
        self.channel_index = 0
        # channel_mask = 1 << channel_index
        self.channel_mask = 0
        self.access_mask = 0
        self.rx_queue_size = rx_queue_size
        self.baud_rate = baud_rate
        vxl_open_driver()
        self.update_driver_config()
        self.set_channel(int(channel))

    def __del__(self):
        """."""
        self.stop()
        vxl_close_driver()

    def get_dll_version(self):
        """Get the version of the vxlAPI.dll."""
        ver = self.driver_config.dllVersion
        major = ((ver & 0xFF000000) >> 24)
        minor = ((ver & 0xFF0000) >> 16)
        build = ver & 0xFFFF
        # return f'{major}.{minor}.{build}'
        return '{}.{}.{}'.format(major, minor, build)

    def set_channel(self, channel):
        """Set the vector hardware channel."""
        self.channel = channel
        self.channel_valid = False
        if not self.driver_config.channelCount:
            logging.error('No available CAN channels!')
        elif self.channel > self.driver_config.channelCount:
            logging.error('Channel {} does not exist!'.format(self.channel))
        else:
            if not self.channel:
                # No channel specified, connect to the last channel which
                # should be virtual
                self.channel = self.driver_config.channelCount
            self.channel_index = self.channel - 1
            self.channel_mask = c_ulonglong(1 << int(self.channel_index))
            self.access_mask = c_ulonglong(1 << int(self.channel_index))
            channel_config = self.driver_config.channel[self.channel_index]
            if channel_config.channelBusCapabilities & CAN_SUPPORTED:
                self.channel_valid = True
            else:
                logging.error('Channel {} doesn\'t support CAN!'
                              ''.format(self.channel))

    def update_driver_config(self):
        """Update the list of connected hardware."""
        vxl_close_driver()
        vxl_open_driver()
        drv_config_ptr = pointer(vxl_driver_config_type())
        vxl_get_driver_config(drv_config_ptr)
        self.driver_config = drv_config_ptr.contents
        logging.debug('Vxl Channels {}'
                      ''.format(self.driver_config.channelCount))

    def start(self):
        """Connect to the CAN channel."""
        if self.channel_valid:
            ph_ptr = pointer(self.port_handle)
            app_name = create_string_buffer('pyvxl.VxlCan', 32)
            perm_mask = c_ulonglong(self.access_mask.value)
            perm_ptr = pointer(perm_mask)
            # portHandle, userName, accessMask, permissionMask, rxQueueSize,
            # interfaceVersion, busType
            self.port_opened = vxl_open_port(ph_ptr, app_name,
                                             self.access_mask, perm_ptr,
                                             self.rx_queue_size, 3,
                                             CAN_BUS_TYPE)
            if not self.port_opened:
                logging.error('Failed to open the port!')
            else:
                # Check if we have init access
                if perm_mask.value == self.channel_mask.value:
                    vxl_set_baudrate(self.port_handle, self.access_mask,
                                     int(self.baud_rate))
                    # vxl_reset_clock(self.port_handle)
                    vxl_flush_tx_queue(self.port_handle, self.access_mask)
                    vxl_flush_rx_queue(self.port_handle)

                # portHandle, accessMask, busType, flags
                if vxl_activate_channel(self.port_handle, self.access_mask,
                                        CAN_BUS_TYPE, 8):
                    self.channel_activated = True
                    txt = 'Successfully connected to Channel {} @ {}Bd!'
                    logging.info(txt.format(self.channel, self.baud_rate))
                else:
                    logging.error('Failed to activate the channel')
        else:
            logging.error('Unable to start with an invalid channel!')

        return self.channel_activated

    def stop(self):
        """Disconnect from the CAN channel."""
        if self.channel_activated:
            vxl_deactivate_channel(self.port_handle, self.access_mask)
            self.channel_activated = False
        if self.port_opened:
            vxl_close_port(self.port_handle)
            self.port_opened = False

    def flush_queues(self):
        """Flush the transmit and receive queues for all connected channels.

        This is useful when the transciever is stuck transmitting a frame
        because it's not being acknowledged. Unfortunately, there's an issue
        with the vxlAPI.dll where this won't work if another program is also
        connected to the same CAN channel. The only way I've found to fix this
        case is by disconnecting all programs from the channel.
        """
        vxl_deactivate_channel(self.port_handle, self.access_mask)
        vxl_flush_tx_queue(self.port_handle, self.access_mask)
        vxl_flush_rx_queue(self.port_handle)
        vxl_activate_channel(self.port_handle, self.access_mask, CAN_BUS_TYPE,
                             8)

    def send(self, msg_id, msg_data):
        """Send a CAN message.

        Type checking on input parameters is intentionally left out to increase
        transmit speed.
        """
        dlc = len(msg_data) / 2
        msg_data = msg_data.decode('hex')
        xl_event = vxl_event_type()
        data = create_string_buffer(msg_data, 8)
        memset(pointer(xl_event), 0, sizeof(xl_event))
        xl_event.tag = c_ubyte(0x0A)
        if msg_id > 0x8000:
            xl_event.tagData.msg.id = c_ulong(msg_id | 0x80000000)
        else:
            xl_event.tagData.msg.id = c_ulong(msg_id)
        xl_event.tagData.msg.dlc = c_ushort(dlc)
        xl_event.tagData.msg.flags = c_ushort(0)
        # Converting from a string to a c_ubyte array
        tmp_ptr = pointer(data)
        data_ptr = cast(tmp_ptr, POINTER(c_ubyte * 8))
        xl_event.tagData.msg.data = data_ptr.contents
        msg_count = c_uint(1)
        msg_ptr = pointer(msg_count)
        event_ptr = pointer(xl_event)
        return vxl_transmit(self.port_handle, self.channel_mask, msg_ptr,
                            event_ptr)

    def receive(self):
        """Receive a CAN message.

        vxl_receive is not reentrant. Protect calls to this function with
        a lock if receive will be called from different tasks in the same
        process.

        Returns:
            A string if data is received, otherwise None.
        """
        data = None
        msg = c_uint(1)
        msg_ptr = pointer(msg)
        rx_event = vxl_event_type()
        rx_event_ptr = pointer(rx_event)
        if vxl_receive(self.port_handle, msg_ptr, rx_event_ptr):
            data = vxl_get_event_str(rx_event_ptr)
        return data

    def get_rx_queue_size(self):
        """Get the number of elements currently in the receive queue."""
        size = c_int(0)
        size_ptr = pointer(size)
        logging.debug(vxl_get_receive_queue_size(self.port_handle, size_ptr))
        logging.debug('Queue Size: {}'.format(size.value))
        return size.value

    def request_chip_state(self):
        """Request the state of the transciever.

        The actual chip state is added to the receive queue around 50ms after
        the request. Call receive to get the updated value.
        """
        return vxl_request_chip_state(self.port_handle, self.channel_mask)

    def get_time(self):
        """."""
        time = c_ulonglong(0)
        time_ptr = pointer(time)
        logging.debug(vxl_get_sync_time(self.port_handle, time_ptr))
        logging.debug('Time: {}'.format(time.value))
        return time.value

    def get_can_channels(self, include_virtual=False):
        """Return a list of connected CAN channels."""
        can_channels = []
        # Update driver config in case more channels were
        # connected since instantiating this object.
        self.update_driver_config()
        virtual_channels_found = False
        # Search through all channels
        for i in range(self.driver_config.channelCount):
            channel_config = self.driver_config.channel[i]
            virtual_channel = bool('Virtual' in channel_config.name)
            if virtual_channel:
                virtual_channels_found = True
            bus_capabilities = channel_config.channelBusCapabilities
            can_supported = bool(bus_capabilities & CAN_SUPPORTED)
            if can_supported:
                if include_virtual or not virtual_channel:
                    if virtual_channels_found:
                        can_channels.append(int(channel_config.channelIndex) -
                                            1)
                    else:
                        can_channels.append(int(channel_config.channelIndex) +
                                            1)

        return can_channels

    def print_config(self, debug=False):
        """Print the current hardware configuration."""
        found_piggy = False
        buff = create_string_buffer(32)
        printf('----------------------------------------------------------\n')
        printf('- %2d channels       Hardware Configuration              -\n',
               self.driver_config.channelCount)
        printf('----------------------------------------------------------\n')
        for i in range(self.driver_config.channelCount):
            if debug:
                chan = str(int(self.driver_config.channel[i].channelIndex))
                print('- Channel Index: ' + chan + ', ')
                chan = hex(int(self.driver_config.channel[i].channelMask))
                print(' Channel Mask: ' + chan + ', ')
            else:
                chan = str(int(self.driver_config.channel[i].channelIndex) + 1)
                print('- Channel: ' + chan + ', ')
            strncpy(buff, self.driver_config.channel[i].name, 23)
            printf(' %23s, ', buff)
            memset(buff, 0, sizeof(buff))
            if self.driver_config.channel[i].transceiverType != 0x0000:
                found_piggy = True
                strncpy(buff, self.driver_config.channel[i].transceiverName,
                        13)
                printf('%13s -\n', buff)
            else:
                printf('    no Cab!   -\n', buff)

        printf('----------------------------------------------------------\n')
        if not found_piggy:
            logging.info('Virtual channels only!')
            return False
        return True
