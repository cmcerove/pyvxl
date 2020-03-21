#!/usr/bin/env python

"""Holds classes designed to interact specific protocols of vxlAPI."""

from pyvxl.vxl_functions import vxl_open_driver, vxl_close_driver
from pyvxl.vxl_functions import vxl_open_port, vxl_close_port
from pyvxl.vxl_functions import vxl_activate_channel, vxl_deactivate_channel
from pyvxl.vxl_functions import vxl_reset_clock, vxl_get_driver_config
from pyvxl.vxl_functions import vxl_transmit, vxl_receive
from pyvxl.vxl_functions import vxl_set_baudrate, vxl_set_transceiver
from pyvxl.vxl_functions import vxl_get_event_str
from pyvxl.vxl_functions import vxl_flush_tx_queue, vxl_flush_rx_queue
from pyvxl.vxl_data_types import vxl_driver_config_type, vxl_event_type

import os
import sys
import logging
from binascii import hexlify, unhexlify
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
        self.rx_queue_size = rx_queue_size
        self.baud_rate = baud_rate
        vxl_open_driver()
        self.update_driver_config()
        self.set_channel(int(channel))

    def __del__(self):
        """."""
        self.stop()
        vxl_close_driver()

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
            channel_config = self.driver_config.channel[self.channel_index]
            if channel_config.channelBusCapabilities & CAN_SUPPORTED:
                self.channel_valid = True
            else:
                logging.error('Channel {} doesn\'t support CAN!'.format(self.channel))

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
            app_name = create_string_buffer('pyvxl', 32)
            perm_mask = c_ulonglong(self.channel_mask.value)
            perm_ptr = pointer(perm_mask)
            # portHandle, userName, accessMask, permissionMask, rxQueueSize,
            # interfaceVersion, busType
            self.port_opened = vxl_open_port(ph_ptr, app_name,
                                             self.channel_mask, perm_ptr,
                                             self.rx_queue_size, 3,
                                             CAN_BUS_TYPE)
            if not self.port_opened:
                logging.error('Failed to open the port!')
            else:
                # Check if we have init access
                if perm_mask.value == self.channel_mask.value:
                    vxl_set_baudrate(self.port_handle, self.channel_mask,
                                     int(self.baud_rate))
                    vxl_reset_clock(self.port_handle)
                    vxl_flush_tx_queue(self.port_handle, self.channel_mask)
                    vxl_flush_rx_queue(self.port_handle)

                # portHandle, accessMask, busType, flags
                if vxl_activate_channel(self.port_handle, self.channel_mask,
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
            vxl_deactivate_channel(self.port_handle, self.channel_mask)
            self.channel_activated = False
        if self.port_opened:
            vxl_close_port(self.port_handle)
            self.port_opened = False

    def reconnect(self):
        """Reconnect to the CAN channel."""
        vxl_deactivate_channel(self.port_handle, self.channel_mask)
        vxl_flush_tx_queue(self.port_handle, self.channel)
        vxl_flush_rx_queue(self.port_handle)
        vxl_activate_channel(self.port_handle, self.channel_mask, CAN_BUS_TYPE,
                             8)

    def high_voltage_wakeup(self):
        """Send a high voltage wakeup message."""
        """
        linModeWakeup = c_uint(0x0007)
        vxl_set_transceiver(self.port_handle, self.channel_mask, c_int(0x0006),
                            linModeWakeup, c_uint(100))
        return True
        """
        raise NotImplementedError

    def send(self, msg_id, msg_data):
        """Send a CAN message."""
        # TODO: Finish moving endianness and update function call to vector
        msg_data = unhexlify(msg_data)
        dlc = len(msg_data)
        if dlc:
            logging.debug('Sending CAN Msg: 0x{0:X} Data: {1}'
                          ''.format(msg_id & ~0x80000000,
                                    hexlify(msg_data).upper()))
        else:
            logging.debug('Sending CAN Msg: 0x{0:X} Data: None'.format(msg_id))

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
        """Receive a CAN message."""
        data = None
        msg = c_uint(1)
        msg_ptr = pointer(msg)
        rx_event = vxl_event_type()
        rx_event_ptr = pointer(rx_event)
        if vxl_receive(self.port_handle, msg_ptr, rx_event_ptr):
            data = str(vxl_get_event_str(rx_event_ptr)).split()
            logging.debug(data)
        return data

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
            can_supported = bool(channel_config.channelBusCapabilities &
                                 CAN_SUPPORTED)
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
                sys.stdout.write('- Channel Index: ' + chan + ', ')
                chan = hex(int(self.driver_config.channel[i].channelMask))
                sys.stdout.write(' Channel Mask: ' + chan + ', ')
            else:
                chan = str(int(self.driver_config.channel[i].channelIndex) + 1)
                sys.stdout.write('- Channel: ' + chan + ', ')
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
