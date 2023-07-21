#!/usr/bin/env python

"""Holds classes designed to interact specific protocols of vxlAPI."""

from pyvxl.vxl_functions import vxl_open_driver, vxl_close_driver
from pyvxl.vxl_functions import vxl_open_port, vxl_close_port, vxl_reset_clock
from pyvxl.vxl_functions import vxl_activate_channel, vxl_deactivate_channel
from pyvxl.vxl_functions import vxl_get_driver_config
from pyvxl.vxl_functions import vxl_transmit, vxl_receive
from pyvxl.vxl_functions import vxl_get_receive_queue_size, vxl_get_sync_time
from pyvxl.vxl_functions import vxl_request_chip_state, vxl_set_fd_conf
from pyvxl.vxl_functions import vxl_flush_tx_queue, vxl_flush_rx_queue
from pyvxl.vxl_types import vxl_driver_config_type, vxl_can_rx_event
from pyvxl.vxl_types import vxl_can_tx_event, vxl_can_fd_conf

import os
import logging
from time import sleep
from ctypes import cdll, c_uint, c_int, c_ubyte, c_ulong, cast
from ctypes import c_ushort, c_ulonglong, pointer, sizeof, POINTER
from ctypes import c_long, create_string_buffer

logger = logging.getLogger(__name__)

# Grab the c library and some functions from it
if os.name == 'nt':
    libc = cdll.msvcrt
printf = libc.printf
strncpy = libc.strncpy
memset = libc.memset

OUTPUT_MODE_SILENT = 0
OUTPUT_MODE_NORMAL = 1

ACTIVATE_NONE = 0
ACTIVATE_RESET_CLOCK = 8

ACTIVATE_BUS_CAN = 1
ACTIVATE_BUS_LIN = 2

BUS_TYPE_CAN = 0x00000001
BUS_TYPE_LIN = 0x00000002
BUS_TYPE_FLEXR = 0x00000004
BUS_TYPE_MOST = 0x00000010
BUS_TYPE_DAIO = 0x00000040
BUS_TYPE_J1708 = 0x00000100
IMPLEMENTED_BUS_TYPES = (BUS_TYPE_CAN,)
BUS_TYPE_NAMES = {BUS_TYPE_CAN: 'CAN', BUS_TYPE_LIN: 'LIN'}

INTERFACE_VERSION_V3 = 3  # CAN, LIN, DAIO and K-Line
INTERFACE_VERSION_V4 = 4  # MOST,CAN FD, Ethernet, FlexRay and ARINC429

# Extended data length. This flag is needed when sending more then 8 bytes or
# of the BRS flag is used.
XL_CAN_TXMSG_FLAG_EDL = 0x0001
# Baudrate switch.
XL_CAN_TXMSG_FLAG_BRS = 0x0002
# This flag is used for Remote-Transmission-Request.
# Only useable for Standard CAN messages.
XL_CAN_TXMSG_FLAG_RTR = 0x0010
# High priority message. Clears all send buffers then transmits.
XL_CAN_TXMSG_FLAG_HIGHPRIO = 0x0080
# Generates a wake up message.
XL_CAN_TXMSG_FLAG_WAKEUP = 0x0200


class Vxl:
    """Base class for connecting to the vxlAPI.dll.

    Contains bus independent functions.
    """

    def __init__(self, rx_queue_size=8192):  # noqa
        self.__port = None
        self.__bus_type = None
        self.__access_mask = c_ulonglong(0)
        self.__channels = {}
        self.rx_queue_size = rx_queue_size
        vxl_open_driver()
        self.update_config()

    def __del__(self):
        """."""
        vxl_close_driver()

    @property
    def port(self):
        """Return the port opened in the dll or None if one isn't opened."""
        return self.__port

    def open_port(self, prog_name):
        """Open a port within the dll."""
        if self.port is not None:
            raise AssertionError('Port already opened.')
        if not self.channels:
            raise AssertionError('No channels to open! Add channels with '
                                 'add_channel before calling open_port.')
        port = c_long(-1)
        ph_ptr = pointer(port)
        app_name = create_string_buffer(prog_name.encode('utf-8'), 32)
        perm_mask = c_ulonglong(self.access_mask.value)
        perm_ptr = pointer(perm_mask)
        if not vxl_open_port(ph_ptr, app_name, self.access_mask, perm_ptr,
                             self.rx_queue_size, INTERFACE_VERSION_V4,
                             self.bus_type):
            raise AssertionError(f'Failed opening port for {prog_name}')
        # Set which channels we have init access on
        for channel in self.__channels.values():
            if perm_mask.value & channel.mask.value:
                channel.init_access = True
            else:
                channel.init_access = False
        self.__port = port

    def close_port(self):
        """Close the port."""
        if self.port is None:
            raise AssertionError('Port already closed.')
        vxl_close_port(self.port)
        self.__port = None

    @property
    def bus_type(self):
        """The bus type (e.g. BUS_TYPE_CAN or BUS_TYPE_LIN)."""
        return self.__bus_type

    @bus_type.setter
    def bus_type(self, bus_type):
        """Set the bus type (e.g. BUS_TYPE_CAN or BUS_TYPE_LIN)."""
        if bus_type not in IMPLEMENTED_BUS_TYPES:
            raise NotImplementedError(f'{bus_type} is not implemented')
        if self.__bus_type is not None:
            raise AssertionError('bus_type already set to '
                                 f'{BUS_TYPE_NAMES[self.bus_type]}. It can '
                                 ' only be set once.')
        self.__bus_type = bus_type

    @property
    def access_mask(self):
        """Get the access mask.

        The access mask is a bitwise OR of each channel mask.
        """
        return self.__access_mask

    @property
    def rx_queue_size(self):
        """The receive queue size.

        There is a single receive queue for all channels.
        """
        return self.__rx_queue_size

    @rx_queue_size.setter
    def rx_queue_size(self, size):
        """Set the receive queue size."""
        if self.port is not None:
            raise AssertionError('Port must be closed to change queue size.')
        if not isinstance(size, int) or isinstance(size, bool):
            raise TypeError(f'Expected int but got {type(size)}')
        elif size < 8192 or size > 524288:
            raise ValueError(f'{size} must be >= 8192 and <= 524288')
        elif size & (size - 1):
            raise ValueError(f'{size} must be a power of 2')
        self.__rx_queue_size = size

    @property
    def config(self):
        """Get the driver configuration."""
        return self.__config

    def update_config(self):
        """Update the list of connected hardware."""
        vxl_close_driver()
        vxl_open_driver()
        drv_config_ptr = pointer(vxl_driver_config_type())
        vxl_get_driver_config(drv_config_ptr)
        self.__config = drv_config_ptr.contents
        logger.debug(f'Vxl Channels: {self.config.channelCount}')

    @property
    def channels(self):
        """A dictionary of channels added to Vxl sorted by channel number."""
        # Return a copy to prevent external modification
        return dict(self.__channels)

    def add_channel(self, **kwargs):
        """Add a channel."""
        if self.port is not None:
            raise AssertionError('Port must be closed to change channels.')
        channel = VxlChannel(self, **kwargs)
        if channel.num in self.__channels:
            raise ValueError(f'{channel.num} has already been added')
        self.__channels[channel.num] = channel
        self.__access_mask.value |= channel.mask.value

    def remove_channel(self, num):
        """Remove a channel."""
        if self.port is not None:
            raise AssertionError('Port must be closed to change channels.')
        if num not in self.__channels:
            raise ValueError(f'{num} has already been removed')
        channel = self.__channels.pop(num)
        self.__access_mask.value &= ~channel.mask.value

    def receive(self):
        """Receive a message.

        vxl_receive is not reentrant. Protect calls to this function with
        a lock if receive will be called from different threads in the same
        process.

        Returns:
            A string if data is received, otherwise None.
        """
        if self.port is None:
            raise AssertionError('Port not opened! Call open_port first.')
        rx_event = vxl_can_rx_event()
        rx_event_ptr = pointer(rx_event)
        response = None
        if vxl_receive(self.port, rx_event_ptr):
            response = rx_event
        return response

    def get_rx_queued_length(self):
        """Get the number of elements currently in the receive queue."""
        if self.port is None:
            raise AssertionError('Port not opened! Call open_port first.')
        size = c_int(0)
        size_ptr = pointer(size)
        logger.debug(vxl_get_receive_queue_size(self.port, size_ptr))
        logger.debug(f'Rx Queued Items: {size.value}')
        return size.value

    def reset_clock(self):
        """Reset time stamps for the open port."""
        if self.port is None:
            raise AssertionError('Port not opened! Call open_port first.')
        return vxl_reset_clock(self.port)

    def get_dll_version(self):
        """Get the version of the vxlAPI.dll."""
        ver = self.config.dllVersion
        major = ((ver & 0xFF000000) >> 24)
        minor = ((ver & 0xFF0000) >> 16)
        build = ver & 0xFFFF
        return f'{major}.{minor}.{build}'

    def get_time(self):
        """Get the time from the dll."""
        time = c_ulonglong(0)
        time_ptr = pointer(time)
        logger.debug(vxl_get_sync_time(self.port, time_ptr))
        logger.debug(f'Time: {time.value}')
        return time.value

    def print_config(self, debug=False):
        """Print the current hardware configuration."""
        found_piggy = False
        print('----------------------------------------------------------')
        print(f'- {self.config.channelCount: 2} channels       Hardware '
              'Configuration              -')
        print('----------------------------------------------------------')
        for i in range(self.config.channelCount):
            channel = self.config.channel[i]
            if debug:
                print(f'- Channel Index: {channel.channelIndex}, ', end='')
                print(f' Channel Mask: {channel.channelMask}, ', end='')
            else:
                print(f'- Channel: {channel.channelIndex + 1}, ', end='')
            name = channel.name.decode('utf-8')
            print(f' {name: >16}, ', end='')
            if channel.transceiverType != 0:
                found_piggy = True
                name = channel.transceiverName.decode('utf-8')
                print(f'{name: >13} -')
            else:
                print('    no Cab!           -')

        print('----------------------------------------------------------')
        if not found_piggy:
            logger.info('Virtual channels only!')
            return False
        return True


class VxlChannel:
    """A channel used by Vxl."""

    def __init__(self, vxl, num=0, baud=500000, data_baud=2000000,  # noqa
                 tseg1_arb=6, tseg2_arb=3, sjw_arb=2,
                 tseg1_data=6, tseg2_data=3, sjw_data=2):
        if not isinstance(vxl, Vxl):
            raise TypeError(f'Expected Vxl but got {type(vxl)}')
        self.__vxl = vxl
        self.__activated = False
        self.num = num
        self.init_access = False
        # For more info on CAN bit timing:
        #   https://www.kvaser.com/lesson/can-bit-timing/
        # The XL Driver Library manual also says this:
        #   "The ratio (tseg1+1)/(tseg1+tseg2+1) specifies the sample point.
        #   The constraint is that (tseg1+tseg2+1) must evenly divide the
        #   80 MHz CAN clock at the desired bitrate. More precisely, the
        #   hardware attempts to determine a prescaler >= 1, such that
        #   (tseg1+tseg2+1)*actualBitrate*prescaler = 80MHz. Where
        #   actualBitrate differs by less than 1:256 from the requested
        #   bitrate.
        self.baud = baud
        self.sjw_arb = sjw_arb
        self.tseg1_arb = tseg1_arb
        self.tseg2_arb = tseg2_arb
        self.data_baud = data_baud
        self.sjw_data = sjw_data
        self.tseg1_data = tseg1_data
        self.tseg2_data = tseg2_data
        self.__fd_conf = None

    def __str__(self):
        """Return a string representation of this channel."""
        return (f'VxlChannel({self.num}, {self.baud})')

    @property
    def vxl(self):
        """The vxl instance containing this port."""
        return self.__vxl

    @property
    def num(self):
        """The number for the channel."""
        return self.__num

    @num.setter
    def num(self, num):
        """Set the number for the channel."""
        if not isinstance(num, int) or isinstance(num, bool):
            raise TypeError(f'Expected int but got {type(num)}')
        elif num < 0:
            raise ValueError(f'{num} must be a postive number')
        if num == 0:
            # Default to virtual channel
            num = self.vxl.config.channelCount
        if self.vxl.bus_type is None:
            raise AssertionError('Vxl.bus_type must be set before channels '
                                 'can be created.')
        if num > self.vxl.config.channelCount:
            raise AssertionError(f'{num} must be less than '
                                 f'{self.vxl.config.channelCount}')
        channel_config = self.vxl.config.channel[num - 1]
        bus_type_selected = self.vxl.bus_type << 16
        if not channel_config.channelBusCapabilities & bus_type_selected:
            raise AssertionError(f'Channel({num}) doesn\'t support bus type '
                                 f'{BUS_TYPE_NAMES[self.vxl.bus_type]}')
        self.__num = num
        self.__mask = c_ulonglong(1 << (num - 1))

    @property
    def mask(self):
        """The mask for the channel."""
        return self.__mask

    @property
    def init_access(self):
        """Whether this channel has init access."""
        return self.__init

    @init_access.setter
    def init_access(self, value):
        """Set init access for this channel."""
        if not isinstance(value, bool):
            raise TypeError(f'Expected bool but got {type(value)}')
        self.__init = value

    @property
    def baud(self):
        """The arbitration baud rate for the channel."""
        return self.__baud

    @baud.setter
    def baud(self, baud):
        """Set the arbitration baud rate for the channel."""
        if not isinstance(baud, int) or isinstance(baud, bool):
            raise TypeError(f'Expected int but got {type(baud)}')
        # TODO: Add checking for valid baud rates
        self.__baud = baud

    @property
    def sjw_arb(self):
        """The arbitration synchronization jump width for the channel."""
        return self.__sjw_arb

    @sjw_arb.setter
    def sjw_arb(self, sjw_arb):
        """Set the arbitration synchronization jump width for the channel."""
        if not isinstance(sjw_arb, int) or isinstance(sjw_arb, bool):
            raise TypeError(f'Expected int but got {type(sjw_arb)}')
        self.__sjw_arb = sjw_arb

    @property
    def tseg1_arb(self):
        """The arbitration time segment 1 for the channel.

        Time segment 1 is the number of quanta before the sample point.
        """
        return self.__tseg1_arb

    @tseg1_arb.setter
    def tseg1_arb(self, tseg1_arb):
        """Set the arbitration time segment 1 for the channel.

        Time segment 1 is the number of quanta before the sample point.
        """
        if not isinstance(tseg1_arb, int) or isinstance(tseg1_arb, bool):
            raise TypeError(f'Expected int but got {type(tseg1_arb)}')
        self.__tseg1_arb = tseg1_arb

    @property
    def tseg2_arb(self):
        """The arbitration time segment 2 for the channel.

        Time segment 2 is the number of quanta after the sample point.
        """
        return self.__tseg2_arb

    @tseg2_arb.setter
    def tseg2_arb(self, tseg2_arb):
        """The arbitration time segment 2 for the channel.

        Time segment 2 is the number of quanta after the sample point.
        """
        if not isinstance(tseg2_arb, int) or isinstance(tseg2_arb, bool):
            raise TypeError(f'Expected int but got {type(tseg2_arb)}')
        self.__tseg2_arb = tseg2_arb

    @property
    def data_baud(self):
        """The data baud rate for the channel."""
        return self.__data_baud

    @data_baud.setter
    def data_baud(self, baud):
        """Set the data baud rate for the channel."""
        if not isinstance(baud, int) or isinstance(baud, bool):
            raise TypeError(f'Expected int but got {type(baud)}')
        # TODO: Add checking for valid baud rates
        self.__data_baud = baud

    @property
    def sjw_data(self):
        """The data synchronization jump width for the channel."""
        return self.__sjw_data

    @sjw_data.setter
    def sjw_data(self, sjw_data):
        """Set the data synchronization jump width for the channel."""
        if not isinstance(sjw_data, int) or isinstance(sjw_data, bool):
            raise TypeError(f'Expected int but got {type(sjw_data)}')
        self.__sjw_data = sjw_data

    @property
    def tseg1_data(self):
        """The data time segment 1 for the channel.

        Time segment 1 is the number of quanta before the sample point.
        """
        return self.__tseg1_data

    @tseg1_data.setter
    def tseg1_data(self, tseg1_data):
        """Set the data time segment 1 for the channel.

        Time segment 1 is the number of quanta before the sample point.
        """
        if not isinstance(tseg1_data, int) or isinstance(tseg1_data, bool):
            raise TypeError(f'Expected int but got {type(tseg1_data)}')
        self.__tseg1_data = tseg1_data

    @property
    def tseg2_data(self):
        """The data time segment 2 for the channel.

        Time segment 2 is the number of quanta after the sample point.
        """
        return self.__tseg2_data

    @tseg2_data.setter
    def tseg2_data(self, tseg2_data):
        """The data time segment 2 for the channel.

        Time segment 2 is the number of quanta after the sample point.
        """
        if not isinstance(tseg2_data, int) or isinstance(tseg2_data, bool):
            raise TypeError(f'Expected int but got {type(tseg2_data)}')
        self.__tseg2_data = tseg2_data

    @property
    def fd_conf(self):
        """The CAN FD configuration for the channel."""
        if self.__fd_conf is None:
            self.__fd_conf = vxl_can_fd_conf()
        self.__fd_conf.arbitrationBitRate = c_uint(self.baud)
        self.__fd_conf.sjwAbr = c_uint(self.sjw_arb)
        self.__fd_conf.tseg1Abr = c_uint(self.tseg1_arb)
        self.__fd_conf.tseg2Abr = c_uint(self.tseg2_arb)
        self.__fd_conf.dataBitRate = c_uint(self.data_baud)
        self.__fd_conf.sjwDbr = c_uint(self.sjw_data)
        self.__fd_conf.tseg1Dbr = c_uint(self.tseg1_data)
        self.__fd_conf.tseg2Dbr = c_uint(self.tseg2_data)
        # Available but currently unused:
        # fd_conf.options
        return self.__fd_conf

    @property
    def activated(self):
        """Whether this channel is activated."""
        return self.__activated

    def activate(self):
        """Activate this channel."""
        if self.activated:
            raise AssertionError(f'{self} is already activated')
        if self.vxl.port is None:
            raise AssertionError('Port not opened! Call open_port first.')
        if self.init_access:
            if not vxl_set_fd_conf(self.vxl.port, self.mask,
                                   pointer(self.fd_conf)):
                raise AssertionError('Failed setting the CAN FD configuration '
                                     f'for {self}')
            if not vxl_flush_tx_queue(self.vxl.port, self.mask):
                raise AssertionError('Failed flushing the tx queue for '
                                     f'{self}')
            if not vxl_flush_rx_queue(self.vxl.port):
                raise AssertionError('Failed flushing the rx queue for '
                                     f'{self}')
        if not vxl_activate_channel(self.vxl.port, self.mask,
                                    self.vxl.bus_type, ACTIVATE_NONE):
            raise AssertionError(f'Failed activating {self}')
        self.__activated = True

    def deactivate(self):
        """Deactivate this channel."""
        if not self.activated:
            raise AssertionError(f'{self} is already deactivated')
        if self.vxl.port is None:
            raise AssertionError('Port not opened! Call open_port first.')
        if not vxl_deactivate_channel(self.vxl.port, self.mask):
            raise AssertionError(f'Failed deactivating {self}')
        self.__activated = False


class VxlCan(Vxl):
    """Extends Vxl with CAN specific functionality."""

    def __init__(self, channel=0, **kwargs):  # noqa
        if 'rx_queue_size' in kwargs:
            super().__init__(kwargs.pop('rx_queue_size'))
        else:
            super().__init__()
        self.bus_type = BUS_TYPE_CAN
        if channel is not None:
            self.add_channel(num=channel, **kwargs)

    def __del__(self):
        """."""
        if self.started:
            self.stop()
        super().__del__()

    def __str__(self):
        """Return a string representation of this channel."""
        return (f'VxlCan({self.channels})')

    @property
    def started(self):
        """True if all channels have been activated."""
        return bool(self.port is not None)

    def start(self):
        """Connect to the CAN channel."""
        self.open_port('pyvxl.VxlCan')
        self.reset_clock()
        for channel in self.channels.values():
            channel.activate()

    def stop(self):
        """Disconnect from the CAN channel."""
        if not self.started:
            raise AssertionError(f'{self} is already stopped.')
        for channel in self.channels.values():
            if channel.activated:
                channel.deactivate()
        self.close_port()

    def flush_queues(self):
        """Flush the transmit and receive queues for all connected channels.

        This is useful when the transciever is stuck transmitting a frame
        because it's not being acknowledged. Unfortunately, there's an issue
        with the vxlAPI.dll where this won't work if another program is also
        connected to the same CAN channel. The only way I've found to fix this
        case is by disconnecting all programs from the channel.
        """
        vxl_deactivate_channel(self.port, self.access_mask)
        vxl_flush_tx_queue(self.port, self.access_mask)
        vxl_flush_rx_queue(self.port)
        vxl_activate_channel(self.port, self.access_mask, BUS_TYPE_CAN,
                             ACTIVATE_NONE)

    def send(self, channel, msg_id, msg_data, brs=False):
        """Send a CAN message.

        Type checking on input parameters is intentionally left out to increase
        transmit speed.
        """
        status = b'XL_ERR_QUEUE_IS_FULL'
        if channel not in self.channels:
            raise ValueError(f'{channel} has not been added through '
                             'add_channel.')
        dlc = int(len(msg_data) / 2)
        msg_data = bytes.fromhex(msg_data)
        # Retry transmitting until the queue isn't full
        while status == b'XL_ERR_QUEUE_IS_FULL':
            xl_event = vxl_can_tx_event()
            memset(pointer(xl_event), 0, sizeof(xl_event))
            xl_event.tag = c_ushort(0x0440)
            if msg_id > 0x7FF:
                xl_event.tagData.canMsg.canId = c_ulong(msg_id | 0x80000000)
            else:
                xl_event.tagData.canMsg.canId = c_ulong(msg_id)

            if brs:
                fd_flags = XL_CAN_TXMSG_FLAG_EDL | XL_CAN_TXMSG_FLAG_BRS
            else:
                fd_flags = 0
            if dlc > 8:
                fd_flags |= XL_CAN_TXMSG_FLAG_EDL
                dlc_map = {12: 9, 16: 10, 20: 11, 24: 12, 32: 13, 48: 14,
                           64: 15}
                if dlc not in dlc_map:
                    raise ValueError(f'{dlc}s larger than 8 must be one of '
                                     f'these values: {dlc_map.values()}')
                dlc = dlc_map[dlc]
            xl_event.tagData.canMsg.msgFlags = c_uint(fd_flags)
            xl_event.tagData.canMsg.dlc = c_ubyte(dlc)
            # Converting from a string to a c_ubyte array
            data = create_string_buffer(msg_data, 64)
            tmp_ptr = pointer(data)
            data_ptr = cast(tmp_ptr, POINTER(c_ubyte * 64))
            xl_event.tagData.canMsg.data = data_ptr.contents
            msg_count = c_uint(1)
            msg_sent = c_uint(0)
            msg_sent_ptr = pointer(msg_sent)
            event_ptr = pointer(xl_event)
            status = vxl_transmit(self.port, self.channels[channel].mask,
                                  msg_count, msg_sent_ptr, event_ptr)
            if status == b'XL_ERR_QUEUE_IS_FULL':
                # Let other threads run. Before this sleep was added, I was
                # seeing 400+ loops in this function until the queue was no
                # longer full. After adding it, there was at most one extra
                # loop. I think this thread is starving something important
                # and the sleep allows it to catch up.
                sleep(0.001)

        return True if status == b'XL_SUCCESS' else False

    def get_can_channels(self, include_virtual=False):
        """Return a list of connected CAN channels."""
        can_channels = []
        # Update driver config in case more channels were
        # connected since instantiating this object.
        self.update_config()
        # Search through all channels
        for i in range(self.config.channelCount):
            channel = self.config.channel[i]
            virtual_channel = bool(b'Virtual' in channel.name)
            bus_capabilities = channel.channelBusCapabilities
            can_supported = bool(bus_capabilities & (BUS_TYPE_CAN << 16))
            if can_supported:
                if include_virtual or not virtual_channel:
                    can_channels.append(int(channel.channelIndex) + 1)
        return can_channels

    def request_chip_state(self):
        """Request the chip state for this channel."""
        if self.port is None:
            raise AssertionError('Port not opened! Call open_port first.')
        # TODO: Add this after implementing LIN. Right now it is unreachable.
        # if self.vxl.bus_type != BUS_TYPE_CAN:
        #     raise NotImplementedError('Requesting the chip state is only '
        #                               'supported for CAN bus types.')
        if not vxl_request_chip_state(self.port, self.access_mask):
            raise AssertionError(f'Failed requesting chip state for {self}')
