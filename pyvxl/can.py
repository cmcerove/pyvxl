#!/usr/bin/env python3

"""Contains the classes CAN, Channel, TransmitThread and ReceiveThread."""

import logging
import re
from os import path
from queue import Queue
from time import localtime, sleep, perf_counter
from threading import Thread, Event, Lock, BoundedSemaphore
# TODO: Look into adding a condition for pausing the main thread while
#       waiting for received messages.
from math import gcd
from pyvxl.vxl import VxlCan
from pyvxl.uds import UDS
from pyvxl.can_types import Database


class CAN(object):
    """."""

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

    def add_channel(self, num=0, baud=500000, db=None):
        """Add a channel."""
        # Default to the a virtual channel
        if num == 0:
            num = self.__vxl.config.channelCount
        channel = Channel(self.__vxl, self.__tx_thread, self.__rx_thread, num,
                          baud, db)
        if num in self.__channels:
            raise ValueError(f'Channel {num} has already been added')
        self.__channels[num] = channel
        # If the receive port has already been started, it needs to be stopped
        # before adding a new channel and restarted after or data won't be
        # received from the new channel.
        self.__tx_lock.acquire()
        self.__rx_lock.acquire()
        if self.__vxl.started:
            self.__vxl.stop()
        self.__vxl.add_channel(num, baud)
        self.__vxl.start()
        self.__rx_thread.add_channel(num, baud)
        self.__rx_lock.release()
        self.__tx_lock.release()
        logging.debug(f'Added {channel}')
        return channel

    def remove_channel(self, num):
        """Remove a channel."""
        if not isinstance(num, int):
            raise TypeError(f'Expected int but got {type(num)}')
        if num not in self.__channels:
            raise ValueError(f'Channel {num} not found')
        channel = self.__channels.pop(num)
        self.__tx_lock.acquire()
        self.__rx_lock.acquire()
        if self.__vxl.started:
            self.__vxl.stop()
        self.__vxl.remove_channel(num)
        if self.__vxl.channels:
            self.__vxl.start()
        self.__rx_thread.remove_channel(num)
        self.__rx_lock.release()
        self.__tx_lock.release()
        logging.debug(f'Removed {channel}')
        return channel

    def start_logging(self, *args, **kwargs):
        """Start logging."""
        return self.__rx_thread.start_logging(*args, **kwargs)

    def stop_logging(self):
        """Stop logging."""
        return self.__rx_thread.stop_logging()

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
    """A transmit only extension of VxlChannel."""

    def __init__(self, vxl, tx_thread, rx_thread, num, baud, db_path):  # noqa
        self.__vxl = vxl
        self.__tx_thread = tx_thread
        self.__rx_thread = rx_thread
        self.__channel = num
        self.baud = baud
        self.db = Database(db_path)
        self.uds = UDS(self)

    def __str__(self):
        """Return a string representation of this channel."""
        return (f'Channel(num={self.channel}, baud={self.baud}, db={self.db})')

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

    def _send(self, msg, send_once=False):
        """Common function for sending a message.

        Protected so additional checks aren't needed on parameters.
        """
        if msg.update_func is not None:
            msg.data = msg.update_func(msg)
        self.__vxl.send(self.channel, msg.id, msg.data)
        if not send_once and msg.period:
            self.__tx_thread.add(self.channel, msg)
        logging.debug('TX: {: >8X} {: <16}'.format(msg.id, msg.data))

    def send_message(self, name_or_id, data=None, period=None, send_once=False):
        """Send a message by name or id."""
        msg = self.db.get_message(name_or_id)
        if data is not None:
            msg.data = data
        if period is not None:
            if msg.sending and period == 0:
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
        self.__tx_thread.remove(self.channel, msg)
        return msg

    def stop_all_messages(self):
        """Stop sending all periodic messages."""
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
        # Set errors_found so this function doesn't return immediately based
        # on a previously received non error frame.
        self.__rx_thread.errors_found = True
        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while self.__rx_thread.errors_found:
                sleep(0.001)
            no_error = True
        else:
            start = perf_counter()
            timeout = float(timeout) / 1000.0
            while (perf_counter() - start) < timeout:
                if not self.__rx_thread.errors_found:
                    no_error = True
                    break
                sleep(0.001)

        return no_error

    def wait_for_error(self, timeout=0, flush=False):
        """Block until an error frame is received."""
        error = False
        # Clear errors_found so this function doesn't return immediately based
        # on a previously received error frame.
        self.__rx_thread.errors_found = False

        if flush:
            self.__rx_thread.flush_queues()

        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while not self.__rx_thread.errors_found:
                sleep(0.001)
            error = True
        else:
            start = perf_counter()
            timeout = float(timeout) / 1000.0
            while (perf_counter() - start) < timeout:
                if self.__rx_thread.errors_found:
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
        return self.__rx_thread.dequeue_msg(self.channel, msg.id, timeout)

    def send_recv(self, tx_id, tx_data, rx_id, timeout=1000, queue_size=1000):
        """Send a message and wait for a response."""
        self.start_queue(rx_id, queue_size)
        self.send_message(tx_id, tx_data)
        _, msg_data = self.dequeue_msg(rx_id, timeout)
        return msg_data


class ReceiveThread(Thread):
    """Thread for receiving CAN messages."""

    def __init__(self, vxl, lock):
        """."""
        super().__init__()
        self.daemon = True
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
        # This lock prevents queues from being removed from self.__msg_queues
        # between the check 'msg_id in self.__msg_queues' and getting
        # the item with self.__msg_queues[msg_id] which usually follows.
        # Adding/replacing a queue in self.__msg_queues is safe since a
        # reference will still exist when self.__msg_queues[msg_id] is called.
        self.__queue_lock = Lock()
        self.__stopped = Event()
        self.__time = 0
        self.__log_path = ''
        self.__log_file = None
        self.__log_errors = False
        self.__log_request = Queue()
        self.errors_found = False
        self.__msg_queues = {}
        self.__sleep_time = 0.1
        self.__bus_status = ''
        self.__tx_err_count = 0
        self.__rx_err_count = 0
        # Check for channel changes once per second and raise an error.
        # The vxlAPI.dll does not properly handle changes to the number of
        # channels after connecting to the dll.
        self.__init_channels = self.__vxl.get_can_channels(True)

    def run(self):
        """Main receive loop."""
        # I've only found 5 different receive frame formats. I will keep this
        # list updated as I find more. All formats have been identical up to
        # the receive time (in nanoseconds), so this common part is checked
        # first.
        #  Type          Channel Time
        # 'CHIP_STATE c=1, t=4308992, ' Chip state frames            (1 total)
        # 'RX_MSG c=1, t=161054720, '   Valid Rx/TX and Error frames (4 total)
        msg_start_pat = re.compile(r'^(\w+)\sc=(\d+),\st=(\d+),\s')
        # Possible bus statuses for chip state frames:
        # 'busStatus= ACTIVE, txErrCnt=8, rxErrCnt=0'
        # 'busStatus= WARNING, txErrCnt=96, rxErrCnt=0'
        # 'busStatus= PASSIVE, txErrCnt=127, rxErrCnt=0'
        chip_pat = re.compile(r'\w+=\s(\w+),\s\w+=(\d+),\s\w+=(\d+)')
        # Valid Transmitted CAN Message:
        # 'id=0147 l=8, 0040800000000000 TX tid=00'
        # Valid Received CAN Message with data:
        # 'id=00D0 l=8, 8C845A61000003D0 tid=00'
        # Valid Received CAN Message without data:
        # 'id=81234567 l=0,  tid=00'
        # The 3 above should match the following pattern.
        rx_tx_pat = re.compile(r'id=(\w+)\sl=(\d),\s(\w+)?\s(TX)?\s*tid=(\w+)')
        # Error Frame:
        # type=0147,  ERROR_FRAME tid=00
        error_pat = re.compile(r'\w+=(\d+),\s+ERROR_FRAME\s\w+=(\d+)')

        log_msgs = []
        elapsed = 0
        while not self.__stopped.wait(self.__sleep_time):
            # Check for changes in CAN hardware once per second
            elapsed += self.__sleep_time
            if elapsed >= 1:
                elapsed = 0
                # TODO: Implement or remove this
                # for chan in self.__vxl.get_can_channels(True):
                #     if chan not in self.__init_channels:
                #         if self.__log_file is not None:
                #             self.__stop_logging()
                #         # TODO: Implement a way to pass this error to the
                #         # main thread.
                #         raise AssertionError('CAN case was connected or '
                #                              'disconnected.')
            # Only modify the log file from the Thread
            if self.__log_request == 'start':
                self.__start_logging()
            elif self.__log_request == 'stop':
                self.__stop_logging()

            data = self.__receive(True)
            while data is not None:
                match = msg_start_pat.search(data)
                if data == 'UNKNOWN':
                    data = self.__receive()
                    continue
                elif not match:
                    logging.error('Received unknown frame format \'{}\'. '
                                  'Skipping...'.format(data))
                    data = self.__receive()
                    continue
                msg_type = match.group(1)
                channel = int(match.group(2)) + 1
                # Convert from nanoseconds to seconds
                time = int(match.group(3)) / 1000000000.0
                self.__time = time
                # Check if the main thread is waiting on a received message
                if self.__wait_args is not None:
                    _, _, end_time = self.__wait_args
                    if time > end_time:
                        # The timeout has expired; wake up the main thread
                        self.__wait_args = None
                        self.__wait_sem.release()
                full_data = data
                data = data.replace(match.group(0), '')
                if msg_type == 'CHIP_STATE':
                    cs = chip_pat.match(data)
                    if cs:
                        self.__bus_status = cs.group(1)
                        self.__tx_err_count = int(cs.group(2))
                        self.__rx_err_count = int(cs.group(3))
                    else:
                        logging.error('Received an unhandled format for '
                                      'CHIP_STATE: {}'.format(data))
                elif msg_type == 'RX_MSG':
                    # log_msgs.append(full_data + '\n')
                    error = error_pat.match(data)
                    if error:
                        self.errors_found = True
                        if not self.__log_errors:
                            data = self.__receive()
                            continue
                        else:
                            raise NotImplementedError
                            # TODO: implement logging error frames
                            # data = self.__receive()
                            # continue
                    self.errors_found = False
                    rx_tx = rx_tx_pat.match(data)
                    if not rx_tx:
                        # id=81234567 l=0,  tid=00
                        logging.error('Unknown rx_tx format: [{}]'
                                      ''.format(full_data))
                        data = self.__receive()
                        continue
                    elif rx_tx.group(4):
                        # TX message
                        msg_id = int(rx_tx.group(1), 16)
                        dlc = rx_tx.group(2)
                        d = rx_tx.group(3)
                        if d:
                            data = ' '.join([d[x:x + 2] for x in range(0,
                                                                       len(d),
                                                                       2)])
                        else:
                            data = ''
                        if self.__log_file:
                            if msg_id > 0x7FF:
                                msg_id = '{:X}x'.format(msg_id & 0x1FFFFFFF)
                            else:
                                msg_id = '{:X}'.format(msg_id)
                            log_msgs.append('{: >11.6f} {}  {: <16}Tx   d {} '
                                            '{}\n'.format(time, channel,
                                                          msg_id, dlc, data))
                    else:
                        # RX message
                        msg_id = int(rx_tx.group(1), 16)
                        dlc = rx_tx.group(2)
                        d = rx_tx.group(3)
                        if d:
                            data = ' '.join([d[x:x + 2] for x in range(0,
                                                                       len(d),
                                                                       2)])
                        else:
                            data = ''
                        # Strip the extended message ID bit
                        msg_id &= 0x1FFFFFFF
                        self.__enqueue_msg(time, channel, msg_id, data)
                        if self.__log_file:
                            if msg_id > 0x7FF:
                                msg_id = '{:X}x'.format(msg_id)
                            else:
                                msg_id = '{:X}'.format(msg_id)
                            log_msgs.append('{: >11.6f} {}  {: <16}Rx   d {} '
                                            '{}\n'.format(time, channel,
                                                          msg_id, dlc, data))
                else:
                    logging.error('Unknown msg_type: {} - full message [{}]'
                                  ''.format(msg_type, data))
                data = self.__receive()
            # Writing to the log is placed after all messages have been
            # received to minimize the frequency of file I/O during
            # this thread. This hopefully favors notifying the main thread a
            # new message was received as fast as possible. The downside is
            # writes to a file are slightly delayed.
            if self.__log_file is not None and log_msgs:
                self.__log_file.writelines(log_msgs)
                log_msgs = []
        if self.__log_file is not None and log_msgs:
            self.__log_file.writelines(log_msgs)
            self.__stop_logging()

    def __del__(self):
        """Close open log file."""
        self.__stopped.set()

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
        logging.debug('__start_logging exit')

    def add_channel(self, channel, baud):
        """Start receiving on a channel."""
        with self.__queue_lock:
            self.__msg_queues[channel] = {}

    def remove_channel(self, channel):
        """Remove a channel; stop receiving on it."""
        with self.__queue_lock:
            self.__msg_queues.pop(channel)

    def start_logging(self, log_path, add_date=True, log_errors=False):
        """Request the thread start logging."""
        if not isinstance(log_path, str):
            raise TypeError('Expected str but got {}'.format(type(log_path)))
        if self.__log_path:
            raise AssertionError('Already logging. Call stop_logging first.')
        directory, _ = path.split(log_path)
        if directory and not path.isdir(directory):
            raise ValueError('{} is not a valid directory!'.format(directory))
        if self.__log_request == 'start' or self.__log_path:
            raise AssertionError('Logging already started. Call stop_logging.')
        elif self.__log_request == 'stop':
            while self.__log_request == 'stop':
                # Wait for the thread to stop the previous log
                sleep(0.1)
        tmstr = localtime()
        hr = tmstr.tm_hour % 12
        mn = tmstr.tm_min
        sc = tmstr.tm_sec
        if add_date:
            log_path = '{}[{}-{}-{}]'.format(log_path, hr, mn, sc)
        self.__log_path = path.abspath(log_path + '.asc')
        self.__log_errors = log_errors
        self.__log_request = 'start'
        return self.__log_path

    def __stop_logging(self):
        """Stop logging. Only called from the run loop of the thread."""
        self.__log_request = None
        old_path = self.__log_path
        self.__log_path = ''
        if self.__log_file is not None and not self.__log_file.closed:
            old_path = self.__log_path
            self.__log_file.flush()
            self.__log_file.close()
            self.__log_file = None
            logging.debug('Logging stopped.')
            if not self.__msg_queues:
                self.__sleep_time = 0.1
                self.__logging = False
        return old_path

    def stop_logging(self):
        """Request the thread stop logging."""
        if self.__log_request == 'start':
            while self.__log_request == 'start':
                # Wait for the thread to start the previous log
                sleep(0.1)
        if self.__log_request != 'stop' and self.__log_path:
            old_path = self.__log_path
            logging.debug('Stop logging requested.')
            self.__log_request = 'stop'
        else:
            old_path = ''
            logging.error('Logging already stopped!')
        return old_path

    def start_queue(self, channel, msg_id, queue_size):
        """Start queuing all data received for msg_id."""
        with self.__queue_lock:
            if channel in self.__msg_queues:
                if msg_id in self.__msg_queues[channel]:
                    self.__msg_queues[channel][msg_id].pop(msg_id)
                self.__msg_queues[channel][msg_id] = Queue(queue_size)
                self.__sleep_time = 0.01
            else:
                logging.error(f'Channel {channel} not found in the rx thread.')

    def stop_queue(self, channel, msg_id):
        """Stop queuing received data for msg_id."""
        with self.__queue_lock:
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
        with self.__queue_lock:
            for channel in self.__msg_queues:
                self.__msg_queues[channel] = {}
            if not self.__log_request and not self.__log_path:
                self.__sleep_time = 0.1

    def __enqueue_msg(self, rx_time, channel, msg_id, data):
        """Put a received message in the queue."""
        with self.__queue_lock:
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
                    logging.error('Queue for 0x{:X} is full. {} wasn\'t added. The'
                                  ' size is set to {}. Increase the size with the '
                                  'max_size kwarg or remove messages more quickly.'
                                  ''.format(msg_id, data, max_size))
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
                logging.debug('wait_sem.acquire()')
                self.__wait_args = (channel, msg_id, end_time)
                self.__wait_sem.acquire()
                logging.debug('wait_sem.acquire() - returned')
            if timeout is None or msg_queues[msg_id].qsize():
                logging.debug('queue.get()')
                rx_time, msg_data = msg_queues[msg_id].get()
                logging.debug('queue.get() - returned')
        else:
            logging.error('Queue for 0x{:X} hasn\'t been started! Call '
                          'start_queuing first.'.format(msg_id))
        return rx_time, msg_data


class TransmitThread(Thread):
    """Thread for transmitting CAN messages."""

    def __init__(self, vxl, lock):
        """."""
        super().__init__()
        self.daemon = True
        self.__vxl = vxl
        self.__lock = lock
        self.__stopped = Event()
        self.__messages = {}
        self.__num_msgs = 0
        self.__set_defaults()

    def run(self):
        """The main loop for the thread."""
        while not self.__stopped.wait(self.__sleep_time_s):
            # sleep(1)
            with self.__lock:
                for channel, msgs in self.__messages.items():
                    for msg in msgs.values():
                        if self.__elapsed % msg.period == 0:
                            if msg.update_func is not None:
                                msg.data = msg.update_func(msg)
                            self.__vxl.send(channel, msg.id, msg.data)
                if self.__elapsed >= self.__max_increment:
                    self.__elapsed = self.__sleep_time_ms
                else:
                    self.__elapsed += self.__sleep_time_ms

    def stop(self):
        """Stop the thread."""
        self.__stopped.set()

    def __set_defaults(self):
        """Set values to defaults when no messages have been added."""
        self.__sleep_time_ms = 1
        self.__sleep_time_s = 1
        self.__max_increment = 0
        self.__elapsed = 0

    def __update_times(self):
        """Update times for the transmit loop."""
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
                curr_gcd = self.__sleep_time_ms
                curr_lcm = self.__max_increment
                prev = msg.period
                for msgs in self.__messages.values():
                    for msg in msgs.values():
                        curr = msg.period
                        tmp_gcd = gcd(prev, curr)
                        tmp_lcm = prev * curr / tmp_gcd
                        if curr_gcd is None or tmp_gcd < curr_gcd:
                            curr_gcd = tmp_gcd
                        if tmp_lcm > curr_lcm:
                            curr_lcm = tmp_lcm
                        prev = curr
                self.__sleep_time_ms = curr_gcd
                self.__sleep_time_s = curr_gcd / 1000.0
                self.__max_increment = curr_lcm
            if self.__elapsed >= self.__max_increment:
                self.__elapsed = self.__sleep_time_ms
        # print(f'sleep time ms: {self.__sleep_time_ms}')
        # print(f'sleep time s:  {self.__sleep_time_s}')
        # print(f'max increment: {self.__max_increment}')

    def add(self, channel, msg):
        """Add a periodic message to the thread."""
        if channel not in self.__messages:
            self.__messages[channel] = {}
        with self.__lock:
            self.__messages[channel][msg.id] = msg
            self.__num_msgs += 1
            self.__update_times()
            msg._set_sending(True)
        logging.debug('TX: {: >8X} {: <16} period={}ms'
                      ''.format(msg.id, msg.data, msg.period))

    def remove(self, channel, msg):
        """Remove a periodic message from the thread."""
        if channel in self.__messages and msg.id in self.__messages[channel]:
            with self.__lock:
                msg = self.__messages[channel].pop(msg.id)
                self.__num_msgs -= 1
                self.__update_times()
                msg._set_sending(False)
            logging.debug(f'Removed periodic message: 0x{msg.id:03X} '
                          f'{msg.data: <16} period={msg.period}ms')
        else:
            logging.debug(f'{msg.name} (0x{msg.id:X}) is not being sent!')

    def remove_all(self, channel):
        """Remove all periodic messages for a specific channel."""
        if channel in self.__messages:
            with self.__lock:
                for msg in self.__messages[channel].values():
                    self.__num_msgs -= 1
                    msg._set_sending(False)
                self.__messages[channel] = {}
                self.__update_times()
