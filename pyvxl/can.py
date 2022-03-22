#!/usr/bin/env python

"""Contains the classes CAN, Channel, TransmitThread and ReceiveThread."""

import logging
import atexit
from os import path, remove
from queue import Queue
from time import localtime, sleep, perf_counter
from threading import Thread, Lock, BoundedSemaphore, Condition
# TODO: Look into adding a condition for pausing the main thread while
#       waiting for received messages.
from math import gcd
from pyvxl.vxl import VxlCan
from pyvxl.uds import UDS
from pyvxl.can_types import Database


class CAN:
    """Simulate one or more CAN channels."""

    __instance_created = False

    def __init__(self):  # noqa
        if CAN.__instance_created:
            raise AssertionError('Due to limitations of the vxlAPI, only '
                                 'one instance of CAN is allowed at a time')
        CAN.__instance_created = True
        self.__channels = {}
        self.__vxl = VxlCan(channel=None)
        self.__tx_lock = Lock()
        self.__tx_thread = TransmitThread(self.__vxl, self.__tx_lock)
        self.__tx_thread.start()
        self.__rx_lock = Lock()
        self.__rx_thread = ReceiveThread(self.__vxl, self.__rx_lock)
        self.__rx_thread.start()

    @property
    def channels(self):
        """A dictionary of added CAN channels by number."""
        # dict is called to prevent editting self.__channels externally.
        return dict(self.__channels)

    @property
    def vxl(self):
        """A reference to the lower layer vxl object."""
        return self.__vxl

    def add_channel(self, num=0, db=None, **kwargs):
        """Add a channel."""
        # Default to the a virtual channel
        if num == 0:
            num = self.__vxl.config.channelCount
        channel = Channel(self.__vxl, self.__tx_thread, self.__rx_thread, num,
                          db)
        if num in self.__channels:
            raise ValueError(f'Channel {num} has already been added')
        self.__channels[num] = channel
        # If the receive port has already been started, it needs to be stopped
        # before adding a new channel and restarted after or data won't be
        # received from the new channel.
        with self.__tx_lock and self.__rx_lock:
            if self.__vxl.started:
                self.__vxl.stop()
            self.__vxl.add_channel(num=num, **kwargs)
            self.__vxl.start()
            self.__rx_thread.add_channel(num)
        logging.debug(f'Added channel {channel}')
        return channel

    def remove_channel(self, num):
        """Remove a channel."""
        if not isinstance(num, int) or isinstance(num, bool):
            raise TypeError(f'Expected int but got {type(num)}')
        if num not in self.__channels:
            raise ValueError(f'Channel {num} not found')
        channel = self.__channels.pop(num)
        with self.__tx_lock and self.__rx_lock:
            if self.__vxl.started:
                self.__vxl.stop()
            self.__vxl.remove_channel(num)
            if self.__vxl.channels:
                self.__vxl.start()
            self.__rx_thread.remove_channel(num)
        logging.debug(f'Removed channel {channel}')
        return channel

    def start_logging(self, *args, **kwargs):
        """Start logging."""
        return self.__rx_thread.start_logging(*args, **kwargs)

    def stop_logging(self, delete_log=False):
        """Stop logging."""
        return self.__rx_thread.stop_logging(delete_log)

    def stop_all_messages(self):
        """Stop transmitting periodic messages on all channels."""
        for channel in self.__channels.values():
            channel.stop_all_messages()

    def print_periodics(self, info=False, search_for=''):
        """Print all periodic messages currently being sent."""
        raise NotImplementedError
        # if search_for:
        #     # pylint: disable=W0612
        #     (status, msgID) = self._checkMsgID(search_for)
        #     if not status:
        #         return False
        #     elif status == 1:  # searching periodics by id
        #         for periodic in self.currentPeriodics:
        #             if periodic.id == msgID:
        #                 self.last_found_msg = periodic
        #                 self._print_msg(periodic)
        #                 for sig in periodic.signals:
        #                     self.last_found_sig = sig
        #                     self._print_sig(sig, value=True)
        #     else:  # searching by string or printing all
        #         found = False
        #         msgID = msgID.lower()
        #         for msg in self.currentPeriodics:
        #             if search_for.lower() in msg.name.lower():
        #                 found = True
        #                 self.last_found_msg = msg
        #                 self._print_msg(msg)
        #                 for sig in msg.signals:
        #                     self.last_found_sig = sig
        #                     self._print_sig(sig, value=True)
        #             else:
        #                 msgPrinted = False
        #                 for sig in msg.signals:
        #                     short_name = (msgID in sig.name.lower())
        #                     full_name = (msgID in sig.long_name.lower())
        #                     if full_name or short_name:
        #                         found = True
        #                         if not msgPrinted:
        #                             self.last_found_msg = msg
        #                             self._print_msg(msg)
        #                             msgPrinted = True
        #                         self.last_found_sig = sig
        #                         self._print_sig(sig, value=True)
        #         if not found:
        #             logging.error(
        #                 'Unable to find a periodic message with that string!')
        # else:
        #     for msg in self.currentPeriodics:
        #         self.last_found_msg = msg
        #         self._print_msg(msg)
        #         if info:
        #             for sig in msg.signals:
        #                 self.last_found_sig = sig
        #                 self._print_sig(sig, value=True)


class Channel:
    """The interface to a channel added through CAN.add_channel."""

    def __init__(self, vxl, tx_thread, rx_thread, num, db_path):  # noqa
        self.__vxl = vxl
        self.__tx_thread = tx_thread
        self.__rx_thread = rx_thread
        self.__channel = num
        self.__name = str(num)
        self.db = Database(db_path)
        self.uds = UDS(self)

    def __str__(self):
        """Return a string representation of this channel."""
        return (f'Channel(num={self.channel}, db={self.db})')

    @property
    def channel(self):
        """The number of this channel."""
        return self.__channel

    @property
    def db(self):
        """The database for this channel."""
        return self.__db

    @db.setter
    def db(self, db):
        """Set the database for this channel."""
        if not isinstance(db, Database):
            raise TypeError(f'Expected {type(Database)} but got {type(db)}')
        self.__db = db

    @property
    def name(self):
        """The name of this channel."""
        return self.__name

    @name.setter
    def name(self, name):
        """Set the name of this channel."""
        if not isinstance(name, str):
            raise TypeError('Expected str but got {}'.format(type(name)))
        self.__name = name

    def _send(self, msg, send_once=False):
        """Common function for sending a message.

        Protected so additional checks aren't needed on parameters.
        """
        if msg.update_func is not None:
            msg.data = msg.update_func(msg)
        self.__vxl.send(self.channel, msg.id, msg.data, msg.brs)
        if not send_once and msg.period:
            self.__tx_thread.add(self.channel, msg)
        logging.info(f'{self.name[:8]: ^8} TX: {msg.id: >8X} {msg.data: <16}')

    def send_message(self, name_or_id, data=None, period=None, send_once=False):
        """Send a message by name or id."""
        msg = self.db.get_message(name_or_id)
        if data is not None:
            msg.data = data
        if period is not None:
            if msg.sending:
                self.stop_message(msg.id)
            msg.period = period
        self._send(msg, send_once)
        return msg

    def send_new_message(self, msg_id, data='', period=0, name='Unknown'):
        """Send a message that isn't in the database.

        After calling this function once for a message, send_message can be
        used since a Message will be created and added to the database.
        """
        msg = self.db.add_message(msg_id, data, period, name)
        self._send(msg)
        return msg

    def stop_message(self, name_or_id):
        """Stop sending a periodic message."""
        msg = self.db.get_message(name_or_id)
        logging.info(f'Stopping message {msg.id: >8X}')
        self.__tx_thread.remove(self.channel, msg)
        return msg

    def stop_all_messages(self):
        """Stop sending all periodic messages."""
        logging.info(f'Stopping messages on {self}')
        self.__tx_thread.remove_all(self.channel)

    def send_signal(self, name, value=None, send_once=False):
        """Send the message containing signal."""
        signal = self.db.get_signal(name)
        if value is not None:
            signal.val = value
        self._send(signal.msg, send_once)
        return signal

    def stop_signal(self, name):
        """Stop transmitting the periodic message containing signal."""
        signal = self.db.get_signal(name)
        self.__tx_thread.remove(self.channel, signal.msg)
        return signal

    def wait_for_no_error(self, timeout=0):
        """Block until a non error frame is received."""
        no_error = False
        # Set the error state so this function doesn't return immediately based
        # on a previously received non error frame.
        self.__rx_thread.set_error_state(self.channel, True)
        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while self.__rx_thread.get_error_state(self.channel):
                sleep(0.001)
            no_error = True
        else:
            start = perf_counter()
            timeout = float(timeout) / 1000.0
            while (perf_counter() - start) < timeout:
                if not self.__rx_thread.get_error_state(self.channel):
                    no_error = True
                    break
                sleep(0.001)

        return no_error

    def wait_for_error(self, timeout=0, flush=False):
        """Block until an error frame is received."""
        error = False
        # Clear the error state so this function doesn't return immediately
        # based on a previously received error frame.
        self.__rx_thread.set_error_state(self.channel, False)
        if flush:
            self.__vxl.flush_queues()

        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while not self.__rx_thread.get_error_state(self.channel):
                sleep(0.001)
            error = True
        else:
            start = perf_counter()
            timeout = float(timeout) / 1000.0
            while (perf_counter() - start) < timeout:
                if self.__rx_thread.get_error_state(self.channel):
                    error = True
                    break
                sleep(0.001)

        if error:
            # As long as there are no other connections (e.g. CANoe) to this
            # channel of the vector hardware, this will clear the error
            # frame from the hardware retransmit buffer.
            self.__vxl.flush_queues()
        return error

    def wait_for_msg(self, name_or_id, timeout=None):
        """Wait for a message to be received.

        Args
            timeout(ms):  If None, block until a message is received.
        """
        self.start_queue(name_or_id)
        _, msg_data = self.dequeue_msg(name_or_id, timeout)
        self.stop_queue(name_or_id)
        return msg_data

    def start_queue(self, name_or_msg_id, queue_size=1000):
        """Start queuing received messages matching name_or_msg_id.

        If a queue is already started, it will be replaced with this new one.
        """
        msg = self.db.get_message(name_or_msg_id)
        self.__rx_thread.start_queue(self.channel, msg.id, queue_size)

    def stop_queue(self, name_or_msg_id):
        """Stop queuing received messages matching name_or_msg_id."""
        msg = self.db.get_message(name_or_msg_id)
        self.__rx_thread.stop_queue(self.channel, msg.id)

    def dequeue_msg(self, name_or_msg_id, timeout=None):
        """Dequeue a received message matching name_or_msg_id.

        Args
            timeout(ms):  If None, block until a message is received.

        Returns
            A tuple in the format:
            ((float)received_time_seconds, (str)received_data)
            If there aren't any queued messages, (None, None) will be returned.
        """
        msg = self.db.get_message(name_or_msg_id)
        rx_time, data = self.__rx_thread.dequeue_msg(self.channel, msg.id,
                                                     timeout)
        if data is not None:
            logging.info(f'{self.name[:8]: ^8} RX: {msg.id: >8X} {data: <16}')
        else:
            logging.info(f'{self.name[:8]: ^8} RX timeout: {msg.id: >8X} was '
                         f'not received after {timeout} milliseconds')
        return rx_time, data

    def send_recv(self, tx_id, tx_data, rx_id, timeout=1000, queue_size=1000):
        """Send a message and wait for a response."""
        self.start_queue(rx_id, queue_size)
        self.send_message(tx_id, tx_data)
        _, msg_data = self.dequeue_msg(rx_id, timeout)
        return msg_data


class ReceiveThread(Thread):
    """Thread for receiving CAN messages."""

    def __init__(self, vxl, lock):  # noqa
        super().__init__(daemon=True)
        self.__vxl = vxl
        self.__rx_lock = lock
        # Format (channel, msg_id, end_time). These are used to tell the
        # receive thread which message the main thread is looking for. If
        # msg_id is not received on channel by end_time, the receive thread
        # will notify the main thread.
        self.__wait_args = None
        # Used for blocking the main thread while waiting for a received
        # message. A BoundedSemaphore was chosen since it will raise a
        # ValueError if there is an error in the receive thread where it
        # releases the semaphore too frequently.
        self.__wait_sem = BoundedSemaphore(1)
        # Decrement the semaphore by 1 so the next call to acquire will
        # block until the receive thread releases it.
        self.__wait_sem.acquire()
        # This lock helps synchronize mutable types that are modified by both
        # threads.
        self.__lock = Lock()
        self.__time = 0
        self.__sleep_time = 0.1
        self.__log_path = ''
        self.__log_file = None
        self.__log_errors = False
        self.__delete_log = False
        self.__log_request = Queue()
        self.__msg_queues = {}

        self.__bus_status = {}
        self.__pending_msgs = []
        # Check for channel changes once per second and raise an error.
        # The vxlAPI.dll does not properly handle changes to the number of
        # channels after connecting to the dll.
        self.__init_channels = self.__vxl.get_can_channels(True)
        atexit.register(self.stop)

    def run(self):
        """Main receive loop."""
        # From vxlapi.h
        XL_CAN_EV_TAG_RX_OK = 0x0400  # noqa
        XL_CAN_EV_TAG_RX_ERROR = 0x0401  # noqa
        XL_CAN_EV_TAG_TX_ERROR = 0x0402  # noqa
        XL_CAN_EV_TAG_TX_REQUEST = 0x0403  # noqa
        XL_CAN_EV_TAG_TX_OK = 0x0404  # noqa
        XL_CAN_EV_TAG_CHIP_STATE = 0x0409  # noqa
        XL_SYNC_PULSE = 0x000B  # noqa
        log_msgs = self.__pending_msgs
        while True:
            sleep(self.__sleep_time)
            # Only modify the log file from the Thread
            if self.__log_request == 'start':
                self.__start_logging()
            elif self.__log_request == 'stop':
                self.__stop_logging()

            rx_event = self.__receive(True)
            while rx_event is not None:
                # rx_event is the type vxl_can_rx_event in vxl_types.py
                channel = rx_event.channelIndex + 1
                # Convert from nanoseconds to seconds
                time = rx_event.timeStampSync / 1000000000.0
                # Currently unused parts of rx_event:
                #   size
                #   userHandle
                #   flagsChip
                self.__time = time
                # Check if the main thread is waiting on a received message
                if self.__wait_args is not None:
                    chan, msg_id, end_time = self.__wait_args
                    queued = self.__msg_queues[chan][msg_id].qsize()
                    if time > end_time or queued:
                        # The timeout has expired; wake up the main thread
                        self.__wait_args = None
                        self.__wait_sem.release()

                if rx_event.tag == XL_CAN_EV_TAG_RX_OK or \
                   rx_event.tag == XL_CAN_EV_TAG_TX_OK:
                    self.set_error_state(channel, False)
                    # Currently unused parts of rx_event:
                    # rx_event.tagData.canRxOkMsg.msgFlags
                    # rx_event.tagData.canRxOkMsg.crc
                    # rx_event.tagData.canRxOkMsg.totalBitCnt
                    msg_id = rx_event.tagData.canRxOkMsg.canId
                    dlc = rx_event.tagData.canRxOkMsg.dlc
                    rx_data = rx_event.tagData.canRxOkMsg.data
                    # Convert rx_data from a ctypes 64 byte array to a string
                    data = ''
                    for i, byte in enumerate(rx_data):
                        if i >= dlc:
                            break
                        elif i > 0:
                            data += f' {byte:02X}'
                        else:
                            data += f'{byte:02X}'
                    # Strip the extended message ID bit
                    msg_id &= 0x1FFFFFFF
                    txrx = 'Tx'
                    if rx_event.tag == XL_CAN_EV_TAG_RX_OK:
                        txrx = 'Rx'
                        self.__enqueue_msg(time, channel, msg_id, data)
                    if self.__log_file is not None:
                        if msg_id > 0x7FF:
                            msg_id = f'{msg_id:X}x'
                        else:
                            msg_id = f'{msg_id:X}'

                        log_msgs.append(f'{time: >11.6f} {channel}  '
                                        f'{msg_id: <16}{txrx}   '
                                        f'd {dlc} {data}\n')
                elif (rx_event.tag == XL_CAN_EV_TAG_RX_ERROR or
                      rx_event.tag == XL_CAN_EV_TAG_TX_ERROR):
                    self.set_error_state(channel, True)
                    # Currently unused. Here's what we have access to:
                    # rx_event.tagData.canError.errorCode
                    if not self.__log_errors:
                        rx_event = self.__receive()
                        continue
                    else:
                        # TODO: implement logging for error frames
                        raise NotImplementedError
                elif rx_event.tag == XL_CAN_EV_TAG_TX_REQUEST:
                    self.set_error_state(channel, False)
                    # Currently unused. Here's what we have access to:
                    # rx_event.tagData.canTxRequest.canId
                    # rx_event.tagData.canTxRequest.msgFlags
                    # rx_event.tagData.canTxRequest.dlc
                    # rx_event.tagData.canTxRequest.data
                elif rx_event.tag == XL_CAN_EV_TAG_CHIP_STATE:
                    self.set_error_state(channel, False)
                    bus_status = rx_event.tagData.canChipState.busStatus
                    tx_err_count = rx_event.tagData.canChipState.txErrorCounter
                    rx_err_count = rx_event.tagData.canChipState.rxErrorCounter
                    self.__set_status(channel, bus_status, tx_err_count,
                                      rx_err_count)
                elif rx_event.tag == XL_SYNC_PULSE:
                    self.set_error_state(channel, False)
                    # Currently unused. Here's what we have access to:
                    # rx_event.tagData.canSyncPulse.pulseCode
                    # rx_event.tagData.canSyncPulse.time
                else:
                    # The XL Driver Library Manual doesn't specify any other
                    # possible tags so this shouldn't happen.
                    logging.error(f'Unknown rx_event.tag: {rx_event.tag}')
                rx_event = self.__receive()
            # Writing to the log is placed after all messages have been
            # received to minimize the frequency of file I/O during
            # this thread. This hopefully favors notifying the main thread a
            # new message was received as fast as possible. The downside is
            # that writes to a file are slightly delayed.
            if self.__log_file is not None and log_msgs:
                self.__log_file.writelines(log_msgs)
                self.__log_file.flush()
                log_msgs.clear()
        if self.__log_file is not None and log_msgs:
            self.__log_file.writelines(log_msgs)
            self.__stop_logging()

    def stop(self):
        """Close open log file."""
        if self.__log_file is not None:
            if self.__pending_msgs:
                logging.debug('writing pending messages to log')
                self.__log_file.writelines(self.__pending_msgs)
                self.__pending_msgs.clear()
            self.__log_file.flush()
            self.__log_file.close()

    def __receive(self, request_chip_state=False):
        """Receive incoming can frames."""
        with self.__rx_lock:
            if self.__vxl.started:
                if self.__msg_queues and request_chip_state:
                    # Requesting the chip state adds a message to the receive
                    # queue. If the chip state is requested as fast as possible,
                    # it will only add a message every 50ms. Since each received
                    # message has a timestamp, this will give a worst case
                    # resolution for self.get_time() of 50ms when no other CAN
                    # traffic is being received.
                    try:
                        self.__vxl.request_chip_state()
                    except AssertionError:
                        # This sometimes fails while the thread is shutting down
                        pass
                data = self.__vxl.receive()
            else:
                data = None
        return data

    def add_channel(self, channel):
        """Start receiving on a channel."""
        with self.__lock:
            self.__msg_queues[channel] = {}
            self.__bus_status[channel] = {'bus_status': 'INACTIVE',
                                          'tx_err_count': 0, 'rx_err_count': 0,
                                          'error_state': False}

    def remove_channel(self, channel):
        """Remove a channel; stop receiving on it."""
        with self.__lock:
            self.__msg_queues.pop(channel)
            self.__bus_status.pop(channel)

    def __set_status(self, channel, bus_status, tx_err_count, rx_err_count):
        """Set the status of a channel from a chip_state message."""
        if channel in self.__bus_status:
            self.__bus_status[channel]['bus_status'] = bus_status
            self.__bus_status[channel]['tx_err_count'] = tx_err_count
            self.__bus_status[channel]['rx_err_count'] = rx_err_count

    def get_status(self, channel):
        """Get information about a channel."""
        status = {}
        if channel in self.__bus_status:
            status['bus_status'] = self.__bus_status[channel]['bus_status']
            status['tx_err_count'] = self.__bus_status[channel]['tx_err_count']
            status['rx_err_count'] = self.__bus_status[channel]['rx_err_count']
        return status

    def set_error_state(self, channel, error_state):
        """Set the error state of a channel."""
        with self.__lock:
            if channel in self.__bus_status:
                self.__bus_status[channel]['error_state'] = error_state

    def get_error_state(self, channel):
        """Get the error state of a channel."""
        error = False
        if channel in self.__bus_status:
            error = self.__bus_status[channel]['error_state']
        return error

    def __start_logging(self):
        """Start logging all traffic."""
        self.__log_request = None
        file_opts = 'w+'
        # Append to the file if it already exists
        if path.isfile(self.__log_path):
            file_opts = 'a'
        self.__log_file = open(self.__log_path, file_opts)
        logging.debug('Logging to: {}'.format(self.__log_path))
        data_str = 'date {} {} {} {}:{}:{} {}\n'
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                  'Sep', 'Oct', 'Nov', 'Dec']
        tmstr = localtime()
        mo = tmstr.tm_mon - 1
        da = tmstr.tm_mday
        wda = tmstr.tm_wday
        yr = tmstr.tm_year
        hr = tmstr.tm_hour % 12
        mn = tmstr.tm_min
        sc = tmstr.tm_sec
        if file_opts == 'w+':
            self.__log_file.write(data_str.format(days[wda], months[mo], da,
                                                  hr, mn, sc, yr))
        self.__log_file.write('base hex  timestamps absolute\n')
        self.__log_file.write('no internal events logged\n')
        self.__sleep_time = 0.01

    def start_logging(self, log_path, add_date=True, log_errors=False):
        """Request the thread start logging."""
        if not isinstance(log_path, str):
            raise TypeError('Expected str but got {}'.format(type(log_path)))
        if not log_path:
            raise ValueError('log_path of "" is invalid')
        if self.__log_request == 'start':
            raise AssertionError('start_logging called twice.')
        elif self.__log_request == 'stop':
            while self.__log_request == 'stop':
                # Wait for the thread to stop the previous log
                sleep(0.1)
        directory, _ = path.split(log_path)
        if directory and not path.isdir(directory):
            raise ValueError('{} is not a valid directory!'.format(directory))
        tmstr = localtime()
        hr = tmstr.tm_hour % 12
        mn = tmstr.tm_min
        sc = tmstr.tm_sec
        if add_date:
            log_path = '{}[{}-{}-{}].asc'.format(log_path, hr, mn, sc)
        self.__log_path = path.abspath(log_path)
        self.__log_errors = log_errors
        self.__log_request = 'start'
        return self.__log_path

    def __stop_logging(self):
        """Stop logging. Only called from the run loop of the thread."""
        old_path = self.__log_path
        if self.__log_file is not None and not self.__log_file.closed:
            self.__log_file.flush()
            self.__log_file.close()
            self.__log_file = None
            if self.__delete_log:
                self.__delete_log = False
                try:
                    remove(old_path)
                except Exception:
                    # The receive thread crashing is hard to debug. This is
                    # safer.
                    pass
            logging.debug('Logging stopped.')
            if not self.__msg_queues:
                self.__sleep_time = 0.1
                self.__logging = False
        self.__log_path = ''
        self.__log_request = None
        return old_path

    def stop_logging(self, delete_log):
        """Request the thread stop logging."""
        if self.__log_request == 'start':
            while self.__log_request == 'start':
                # Wait for the thread to start the previous log
                sleep(0.1)
        if self.__log_request != 'stop' and self.__log_path:
            old_path = self.__log_path
            logging.debug('Stop logging requested.')
            self.__log_request = 'stop'
            self.__delete_log = delete_log
        else:
            old_path = ''
            logging.error('Logging already stopped!')
        return old_path

    def start_queue(self, channel, msg_id, queue_size):
        """Start queuing all data received for msg_id."""
        with self.__lock:
            if channel in self.__msg_queues:
                if msg_id in self.__msg_queues[channel]:
                    self.__msg_queues[channel].pop(msg_id)
                self.__msg_queues[channel][msg_id] = Queue(queue_size)
                self.__sleep_time = 0.01
            else:
                logging.error(f'Channel {channel} not found in the rx thread.')

    def stop_queue(self, channel, msg_id):
        """Stop queuing received data for msg_id."""
        with self.__lock:
            if channel in self.__msg_queues:
                self.__msg_queues[channel].pop(msg_id)
                for channel in self.__msg_queues:
                    if not self.__msg_queues[channel]:
                        queuing = True
                        break
                else:
                    queuing = False
                if not queuing and not self.__log_request and not self.__log_path:
                    self.__sleep_time = 0.1
            else:
                logging.error(f'Channel {channel} not found in the rx thread.')

    def stop_channel_queues(self, channel):
        """Stop all queues for a channel."""
        if channel in self.__msg_queues:
            self.__msg_queues[channel] = {}
        else:
            logging.error(f'Channel {channel} not found in the rx thread.')

    def stop_all_queues(self):
        """Stop all queues."""
        with self.__lock:
            for channel in self.__msg_queues:
                self.__msg_queues[channel] = {}
            if not self.__log_request and not self.__log_path:
                self.__sleep_time = 0.1

    def __enqueue_msg(self, rx_time, channel, msg_id, data):
        """Put a received message in the queue."""
        with self.__lock:
            if channel in self.__msg_queues:
                msg_queues = self.__msg_queues[channel]
            else:
                msg_queues = []
            if msg_id in msg_queues:
                # logging.debug('RX: {: >8X} {: <16}'.format(msg_id, data))
                if not msg_queues[msg_id].full():
                    # logging.debug('queue.put()')
                    msg_queues[msg_id].put((rx_time, data.replace(' ', '')))
                    # logging.debug('queue.put() - returned')
                else:
                    max_size = msg_queues[msg_id].maxsize
                    logging.error(f'Queue for 0x{msg_id:X} is full. {data} '
                                  'wasn\'t added. The size is set to '
                                  f'{max_size}. Increase the size with the '
                                  'max_size kwarg or remove messages more '
                                  'quickly.')
                # Check if the main thread is waiting on a received message
                if self.__wait_args is not None:
                    wait_channel, wait_id, _ = self.__wait_args
                    # The message was received; wake up the main thread
                    if channel == wait_channel and msg_id == wait_id:
                        # logging.debug('__enqueue clearing wait args')
                        self.__wait_args = None
                        self.__wait_sem.release()

    def dequeue_msg(self, channel, msg_id, timeout):
        """Get queued message data in the order it was received.

        Args:
            channel the
            msg_id is received on.
            timeout in ms
        """
        rx_time = msg_data = None
        if channel in self.__msg_queues:
            msg_queues = self.__msg_queues[channel]
        else:
            msg_queues = []
        if msg_id in msg_queues:
            if timeout is not None:
                while self.__time is None:
                    sleep(0.01)
                end_time = self.__time + (timeout / 1000)
                # logging.debug('wait_sem.acquire()')
                self.__wait_args = (channel, msg_id, end_time)
                self.__wait_sem.acquire()
                # logging.debug('wait_sem.acquire() - returned')
            if timeout is None or msg_queues[msg_id].qsize():
                # logging.debug('queue.get()')
                rx_time, msg_data = msg_queues[msg_id].get()
                # logging.debug('queue.get() - returned')
        else:
            logging.error('Queue for 0x{:X} hasn\'t been started! Call '
                          'start_queuing first.'.format(msg_id))
        return rx_time, msg_data


class TransmitThread(Thread):
    """Thread for transmitting CAN messages."""

    def __init__(self, vxl, lock):  # noqa
        super().__init__(daemon=True)
        self.__vxl = vxl
        self.__lock = lock
        self.__messages = {}
        self.__num_msgs = 0
        self.__set_defaults()
        self.__updated = Condition(self.__lock)

    def run(self):
        """The main loop for the thread."""
        time_wasted = 0
        while True:
            start = perf_counter()
            with self.__lock:
                if time_wasted < self.__sleep_time_s and \
                   self.__updated.wait(self.__sleep_time_s - time_wasted):
                    time_wasted += perf_counter() - start
                else:
                    time_wasted = 0
                    for channel, msgs in self.__messages.items():
                        for msg in msgs.values():
                            if self.__elapsed % msg.period == 0:
                                if msg.update_func is not None:
                                    msg.data = msg.update_func(msg)
                                self.__vxl.send(channel, msg.id, msg.data,
                                                msg.brs)
                    if self.__elapsed >= self.__max_increment:
                        self.__elapsed = self.__sleep_time_ms
                    else:
                        self.__elapsed += self.__sleep_time_ms

    def __set_defaults(self):
        """Set values to defaults when no messages have been added."""
        self.__sleep_time_ms = 1000
        self.__sleep_time_s = 1
        self.__max_increment = 0
        self.__elapsed = 0

    def __update_times(self):
        """Update times for the transmit loop."""
        old_sleep_time = self.__sleep_time_s
        if self.__num_msgs == 0:
            self.__set_defaults()
        else:
            # Grab any message to use as starting values
            for msgs in self.__messages.values():
                if msgs:
                    msg = list(msgs.values())[0]
                    break
            else:
                raise AssertionError('__num_msgs is out of sync')
            self.__sleep_time_ms = msg.period
            self.__sleep_time_s = msg.period / 1000.0
            self.__max_increment = msg.period
            if self.__num_msgs > 1:
                msg_start = msg
                curr_gcd = self.__sleep_time_ms
                curr_lcm = self.__max_increment
                prev = msg.period
                for msgs in self.__messages.values():
                    for msg in msgs.values():
                        if msg is msg_start:
                            continue
                        curr = msg.period
                        tmp_gcd = gcd(curr_gcd, curr)
                        tmp_lcm = int(prev * curr / gcd(prev, curr))
                        if tmp_gcd < curr_gcd:
                            curr_gcd = tmp_gcd
                        if tmp_lcm > curr_lcm:
                            curr_lcm = tmp_lcm
                        prev = curr
                self.__sleep_time_ms = curr_gcd
                self.__sleep_time_s = curr_gcd / 1000.0
                self.__max_increment = curr_lcm
            if self.__elapsed >= self.__max_increment:
                self.__elapsed = self.__sleep_time_ms
        if old_sleep_time != self.__sleep_time_s:
            self.__updated.notify()

    def add(self, channel, msg):
        """Add a periodic message to the thread."""
        if channel not in self.__messages:
            self.__messages[channel] = {}
        with self.__lock:
            if msg.id not in self.__messages[channel]:
                self.__num_msgs += 1
            self.__messages[channel][msg.id] = msg
            self.__update_times()
            msg._set_sending(True)
            logging.info(f'Periodic added: {msg.id: >8X} {msg.data: <16} '
                         f'period={msg.period}ms')

    def remove(self, channel, msg):
        """Remove a periodic message from the thread."""
        if channel in self.__messages and msg.id in self.__messages[channel]:
            with self.__lock:
                msg = self.__messages[channel].pop(msg.id)
                self.__num_msgs -= 1
                self.__update_times()
                msg._set_sending(False)
            logging.info(f'Periodic removed: {msg.id: >8X} {msg.data: <16} '
                         f'period={msg.period}ms')
        else:
            logging.warning(f'{msg.name} (0x{msg.id:X}) is not being sent!')

    def remove_all(self, channel):
        """Remove all periodic messages for a specific channel."""
        if channel in self.__messages:
            with self.__lock:
                for msg in self.__messages[channel].values():
                    self.__num_msgs -= 1
                    msg._set_sending(False)
                self.__messages[channel] = {}
                self.__update_times()
