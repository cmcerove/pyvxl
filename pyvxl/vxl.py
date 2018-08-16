#!/usr/bin/env python

"""Holds classes designed to interact specific protocols of vxlAPI."""

from pyvxl.vxl_functions import vxl_open_driver, vxl_close_driver, vxl_open_port, vxl_close_port
from pyvxl.vxl_functions import vxl_activate_channel, vxl_deactivate_channel, vxl_reset_clock
from pyvxl.vxl_functions import vxl_transmit, vxl_receive, vxl_get_driver_config
from pyvxl.vxl_functions import vxl_set_baudrate, vxl_set_transceiver, vxl_get_event_str
from pyvxl.vxl_functions import vxl_flush_tx_queue, vxl_flush_rx_queue
from pyvxl.vxl_data_types import vxl_driver_config_type, vxl_event_type

import os
import sys
import logging
from time import sleep
from binascii import hexlify, unhexlify
from ctypes import cdll, CDLL, c_uint, c_int, c_ubyte, c_ulong, cast
from ctypes import c_ushort, c_ulonglong, pointer, sizeof, POINTER
from ctypes import c_long, create_string_buffer

# Grab the c library and some functions from it
if os.name == 'nt':
    libc = cdll.msvcrt
else:
    libc = CDLL("libc.so.6")
printf = libc.printf
strncpy = libc.strncpy
memset = libc.memset
memcpy = libc.memcpy

CAN_SUPPORTED = 0x10000
CAN_BUS_TYPE = 1

logging.basicConfig(level=logging.DEBUG)


class VxlCan(object):
    """."""

    def __init__(self, channel=0, baudrate=500000, dbc='', rx_queue_size=8192):
        """."""
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
        self.baudrate = baudrate
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
        if not self.driver_config.channelCount:
            logging.error("No available CAN channels!")
        elif self.channel > self.driver_config.channelCount:
            logging.error("Channel {} does not exist!".format(self.channel))
        else:
            if not self.channel:
                # No channel specified, connect to the last channel which should be virtual
                self.channel = self.driver_config.channelCount
            self.channel_index = self.channel - 1
            self.channel_mask = c_ulonglong(1 << int(self.channel_index))
            channel_config = self.driver_config.channel[self.channel_index]
            if channel_config.channelBusCapabilities & CAN_SUPPORTED:
                self.channel_valid = True
            else:
                self.channel_valid = False
                logging.error("Channel {} doesn't support CAN!".format(self.channel))

    def update_driver_config(self):
        """Update the list of connected hardware."""
        drvPtr = pointer(vxl_driver_config_type())
        vxl_get_driver_config(drvPtr)
        self.driver_config = drvPtr.contents
        logging.debug('Channel count {}'.format(self.driver_config.channelCount))

    def start(self, display=False):
        """Connect to the CAN channel."""
        if self.channel_valid:
            ph_ptr = pointer(self.port_handle)
            app_name = create_string_buffer("pyvxl", 32)
            perm_mask = c_ulonglong(self.channel_mask.value)
            perm_ptr = pointer(perm_mask)
            # portHandle, userName, accessMask, permissionMask, rxQueueSize,
            # interfaceVersion, busType
            self.port_opened = vxl_open_port(ph_ptr, app_name, self.channel_mask, perm_ptr,
                                             self.rx_queue_size, 3, CAN_BUS_TYPE)
            if not self.port_opened:
                logging.error("Failed to open the port!")
            else:
                # Check if we have init access
                if perm_mask.value == self.channel_mask.value:
                    vxl_set_baudrate(self.port_handle, self.channel_mask, int(self.baudrate))
                    vxl_reset_clock(self.port_handle)
                    vxl_flush_tx_queue(self.port_handle, self.channel_mask)
                    vxl_flush_rx_queue(self.port_handle)

                # portHandle, accessMask, busType, flags
                if vxl_activate_channel(self.port_handle, self.channel_mask, CAN_BUS_TYPE, 8):
                    self.channel_activated = True
                    txt = 'Successfully connected to Channel {} @ {}Bd!'
                    logging.info(txt.format(self.channel, self.baudrate))
                else:
                    logging.error("Failed to activate the channel")
        else:
            logging.error("Unable to start with an invalid channel!")

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
        vxl_activate_channel(self.port_handle, self.channel_mask, CAN_BUS_TYPE, 8)

    def high_voltage_wakeup(self):
        """Send a high voltage wakeup message."""
        # TODO: Check that we're connected. Needs testing.
        raise NotImplementedError
        linModeWakeup = c_uint(0x0007)
        vxl_set_transceiver(self.port_handle, self.channel_mask, c_int(0x0006),
                            linModeWakeup, c_uint(100))
        return True

    def send(self, msg_id, msg_data):
        """Send a CAN message."""
        # TODO: Finish moving endianness and update function call to vector
        msg_data = unhexlify(msg_data)
        dlc = len(msg_data)
        if dlc:
            logging.debug("Sending CAN Msg: 0x{0:X} Data: {1}".format(msg_id & ~0x80000000,
                         hexlify(msg_data).upper()))
        else:
            logging.debug("Sending CAN Msg: 0x{0:X} Data: None".format(msg_id))

        xlEvent = vxl_event_type()
        data = create_string_buffer(msg_data, 8)
        memset(pointer(xlEvent), 0, sizeof(xlEvent))
        xlEvent.tag = c_ubyte(0x0A)
        if msg_id > 0x8000:
            xlEvent.tagData.msg.id = c_ulong(msg_id | 0x80000000)
        else:
            xlEvent.tagData.msg.id = c_ulong(msg_id)
        xlEvent.tagData.msg.dlc = c_ushort(dlc)
        xlEvent.tagData.msg.flags = c_ushort(0)
        # Converting from a string to a c_ubyte array
        tmpPtr = pointer(data)
        dataPtr = cast(tmpPtr, POINTER(c_ubyte * 8))
        xlEvent.tagData.msg.data = dataPtr.contents
        msgCount = c_uint(1)
        msgPtr = pointer(msgCount)
        eventPtr = pointer(xlEvent)
        vxl_transmit(self.port_handle, self.channel_mask, msgPtr, eventPtr)

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

    def print_config(self):
        """Print the current hardware configuration."""
        foundPiggy = False
        buff = create_string_buffer(32)
        printf("----------------------------------------------------------\n")
        printf("- %2d channels       Hardware Configuration              -\n",
               self.driver_config.channelCount)
        printf("----------------------------------------------------------\n")
        for i in range(self.driver_config.channelCount):
            chan = str(int(self.driver_config.channel[i].channelIndex))
            sys.stdout.write('- Channel Index: ' + chan + ', ')
            chan = hex(int(self.driver_config.channel[i].channelMask))
            sys.stdout.write(' Channel Mask: ' + chan + ', ')
            strncpy(buff, self.driver_config.channel[i].name, 23)
            printf(" %23s, ", buff)
            memset(buff, 0, sizeof(buff))
            if self.driver_config.channel[i].transceiverType != 0x0000:
                foundPiggy = True
                strncpy(buff, self.driver_config.channel[i].transceiverName, 13)
                printf("%13s -\n", buff)
            else:
                printf("    no Cab!   -\n", buff)

        printf("----------------------------------------------------------\n")
        if not foundPiggy:
            logging.info("Virtual channels only!")
            return False


if __name__ == '__main__':
    vxl_can = VxlCan()
    vxl_can.print_config()
    vxl_can.start()
    try:
        while True:
            sleep(1)
            while vxl_can.receive():
                pass
    except KeyboardInterrupt:
        pass
