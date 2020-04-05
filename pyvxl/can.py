#!/usr/bin/env python

"""Contains the CAN class for interacting with vector hardware."""

import traceback
import logging
import re
from os import path
from sys import stdout
from queue import Queue
from time import localtime, sleep
from threading import Thread, Event, RLock
# Condition
from fractions import gcd
from pyvxl.pydbc import import_dbc, DBCMessage
from pyvxl.vxl import VxlCan
from colorama import init, deinit, Fore, Back, Style


class CAN(object):
    """A class for transmitting or receiving CAN.

    Features:
        - Import and search databases (only .dbc is supported)
        - Transmit messages by (periodic messages will transmit periodically):
            - Imported message name or id (send_message)
            - Imported signal name (send_signal)
        - Receive message by:
            - TODO: Finish filling out
    """

    # Synchronizes calls to VxlCan.receive since it's not reentrant
    __rx_lock = None

    def __init__(self, channel=0, db_path=None, baud_rate=500000):
        """."""
        self.vxl = VxlCan(channel, baud_rate)
        self.vxl.start()
        self.__db_path = db_path
        if CAN.__rx_lock is None:
            CAN.__rx_lock = RLock()
        self.__tx_thread = TransmitThread(self.vxl)
        self.__tx_thread.start()
        self.__rx_thread = ReceiveThread(self.vxl, CAN.__rx_lock)
        self.__rx_thread.start()
        init()

    def __del__(self):
        """."""
        deinit()

    def __requires(self, properties):
        """Check that required properties exist."""
        pass

    @property
    def channels(self):
        """A dictionary of CAN channels."""
        return self.__channels

    @property
    def dbs(self):
        """A list of databases ordered by channel."""
        return self.__dbs

    def add_channel(self, num=0, baud=500000, db=''):
        """."""
        # Raise an error if the channel doesn't exist
        pass

    def import_db(self, db_path=None):
        """Import the database."""
        if db_path is not None:
            self.__db_path = db_path
        elif self.__db_path is None:
            raise ValueError('No database path specified!')
        if not isinstance(self.__db_path, str):
            raise TypeError('Expected str but got {}'
                            ''.format(type(self.__db_path)))
        if not path.isfile(self.__db_path):
            raise ValueError('Database {} does not exist'
                             ''.format(self.__db_path))

        try:
            self.imported = import_dbc(self.__db_path)
            logging.info('Successfully imported: {}'
                         ''.format(path.basename(self.__db_path)))
        except Exception:
            self.imported = None
            logging.error('Import failed!')
            logging.info('-' * 60)
            traceback.print_exc(file=stdout)
            logging.info('-' * 60)
            raise

    def start_logging(self, *args, **kwargs):
        """Start logging."""
        return self.__rx_thread.start_logging(*args, **kwargs)

    def stop_logging(self):
        """Stop logging."""
        return self.__rx_thread.stop_logging()

    def _send(self, msg, send_once=False):
        """Send a message."""
        if msg.update_func is not None:
            msg.set_data(msg.update_func(msg))
        data = msg.get_data()
        self.vxl.send(msg.id, data)
        if not send_once and msg.period:
            self.__tx_thread.add(msg)
        logging.debug('TX: {: >8X} {: <16}'.format(msg.id, data))

    def send_message(self, msg_id, data='', period=0, send_once=False,
                     in_database=True):
        """Send a message by name or id."""
        msg = self._get_message_obj(msg_id, data, period, in_database)
        self._send(msg, send_once)

    def stop_message(self, msg_id):
        """Stop sending a periodic message.

        Args:
            msg_id: message name or message id
        """
        msg = self._get_message_obj(msg_id)
        self.__tx_thread.remove(msg)

    def stop_all_messages(self):
        """Stop sending all periodic messages."""
        self.__tx_thread.remove_all()

    def send_signal(self, signal, value, send_once=False, force=False):
        """Send the message containing signal."""
        msg = self._check_signal(signal, value, force)
        self._send(msg, send_once)

    def stop_signal(self, signal):
        """Stop transmitting the periodic message containing signal."""
        msg = self._check_signal(signal)
        self.__tx_thread.remove(msg)

    def _check_node(self, node):
        """Check if a node is valid."""
        if self.imported is None:
            raise AssertionError('No database imported! Call import_db first.')
        if node.lower() not in self.imported.nodes:
            raise ValueError('Node named: {} not found in {}'
                             ''.format(node, self.__db_path))

    def start_node(self, node):
        """Start transmitting all periodic messages sent by node."""
        raise NotImplementedError

    def stop_node(self):
        """Stop transmitting all periodic messages sent by node."""
        raise NotImplementedError

    def find_node(self, node, display=False):
        """Prints all nodes of the dbc matching 'node'"""
        if not self.imported:
            logging.error('No CAN databases currently imported!')
            return False
        (status, node) = self._checkMsgID(node)
        if status == 0:
            return False
        num_found = 0
        for anode in self.imported.nodes.values():
            if status == 1:
                if node == anode.source_id:
                    num_found += 1
                    self.last_found_node = anode
            else:
                if node.lower() in anode.name.lower():#pylint: disable=E1103
                    num_found += 1
                    self.last_found_node = anode
                    if display:
                        txt = Fore.MAGENTA+Style.DIM+'Node: '+anode.name
                        txt2 = ' - ID: '+hex(anode.source_id)
                        print(txt+txt2+Fore.RESET+Style.RESET_ALL)
        if num_found == 0:
            self.last_found_node = None
            logging.info('No nodes found for that input')
        elif num_found > 1:
            self.last_found_node = None

    def find_message(self, msg, display=False, exact=True):
        """Find all messages matching 'msg'."""
        self.last_found_msg = None
        num_found = 0
        msg_id = self._check_type(msg)
        if isinstance(msg_id, int) or isinstance(msg_id, long):
            try:
                if msg_id > 0x8000:
                    # msg_id = (msg_id&~0xF0000FFF)|0x80000000
                    msg_id |= 0x80000000
                    msg = self.imported.messages[msg_id]
                else:
                    msg = self.imported.messages[msg_id]
                num_found += 1
                self.last_found_msg = msg
                if display:
                    self._print_msg(msg)
                    for sig in msg.signals:
                        self._print_sig(sig)
            except KeyError:
                logging.error('Message ID 0x{:X} not found!'.format(msg_id))
                self.last_found_msg = None
                return False
        else:
            for msg in self.imported.messages.values():
                if not exact:
                    if msg_id.lower() in msg.name.lower():
                        num_found += 1
                        self.last_found_msg = msg
                        if display:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
                else:
                    if msg_id.lower() == msg.name.lower():
                        num_found += 1
                        self.last_found_msg = msg
                        if display:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
        if num_found == 0:
            self.last_found_msg = None
            if display:
                logging.info('No messages found for that input')
        elif num_found > 1:
            self.last_found_msg = None
        return True

    def find_signal(self, search_str, display=False, exact=False):
        """Prints all signals of the dbc matching 'search_str'"""
        if not search_str or (type(search_str) != type('')):
            logging.error('No search string found!')
            return False
        if not self.imported:
            logging.warning('No CAN databases currently imported!')
            return False
        num_found = 0
        for msg in self.imported.messages.values():
            msgPrinted = False
            for sig in msg.signals:
                if not exact:
                    short_name = (search_str.lower() in sig.name.lower())
                    full_name = (search_str.lower() in sig.full_name.lower())
                else:
                    short_name = (search_str.lower() == sig.name.lower())
                    full_name = (search_str.lower() == sig.full_name.lower())
                if full_name or short_name:
                    num_found += 1
                    self.last_found_sig = sig
                    self.last_found_msg = msg
                    if display:
                        if not msgPrinted:
                            self._print_msg(msg)
                            msgPrinted = True
                        self._print_sig(sig)
        if num_found == 0:
            self.last_found_sig = None
            logging.info('No signals found for that input')
        elif num_found > 1:
            self.last_found_sig = None
        return True

    def get_message(self, msg):
        """Get the message object by name or id."""
        ret = None
        if self.find_message(msg, exact=True) and self.last_found_msg:
            ret = self.last_found_msg
        return ret

    def get_signals(self, search_str):
        """ Returns a list of signals objects associated with message search_str

        search_str (string): the message name whose signals will be returned
        """
        ret = None
        if self.find_message(search_str, exact=True) and self.last_found_msg:
            ret = self.last_found_msg.signals
        return ret

    def get_signal_values(self, search_str):
        """ Returns a dictionary of values associated with signal search_str

        search_str (string): the signal name whose values will be returned
        """
        ret = None
        if self.find_signal(search_str, exact=True) and self.last_found_sig:
            ret = self.last_found_sig.values
        return ret

    def wait_for_no_error(self, timeout=0):
        """Block until the CAN bus comes out of an error state."""
        errors_found = True
        if not self.receiving:
            self.receiving = True
            self.stopRxThread = Event()
            self.rxthread = ReceiveThread(self.stopRxThread, self.portHandle,
                                          self.locks[0])
            self.rxthread.start()

        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while self.rxthread.errors_found:
                time.sleep(0.001)
            errors_found = False
        else:
            startTime = time.clock()
            timeout = float(timeout) / 1000.0
            while (time.clock() - startTime) < timeout:
                if not self.rxthread.errors_found:
                    errors_found = False
                    break
                time.sleep(0.001)

        # If we started the rx thread, stop it now that we're done
        if not self.rxthread.busy():
            self.stopRxThread.set()
            self.receiving = False
        return errors_found

    def wait_for_error(self, timeout=0, flush=False):
        """ Blocks until the CAN bus goes into an error state """
        errors_found = False
        self.rxthread.errors_found = False

        if flush:
            flushRxQueue(self.portHandle)

        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while not self.rxthread.errors_found:
                time.sleep(0.001)
            errors_found = True
        else:
            startTime = time.clock()
            timeout = float(timeout) / 1000.0
            while (time.clock() - startTime) < timeout:
                if self.rxthread.errors_found:
                    errors_found = True
                    break
                time.sleep(0.001)

        # If there are errors, reconnect to the CAN case to clear the error queue
        if errors_found:
            log_path = ''
            if self.receiving and self.rxthread.logging:
                log_path = self.rxthread.stopLogging()

            self.stop()
            self.start()

            if log_path:
                self.start_logging(log_path, add_date=False)
            self.rxthread.errors_found = False
        return errors_found

    def _block_unless_found(self, msgID, timeout):
        foundData = ''
        startTime = time.clock()
        timeout = timeout / 1000.0

        while (time.clock() - startTime) < timeout:
            time.sleep(0.01)
            foundData = self.rxthread.getFirstRxMessage(msgID)
            if foundData:
                break

        if foundData:
            return foundData
        else:
            return False

    def wait_for(self, msgID, data, timeout, alreadySearching=False,
                 in_database=True):
        """Compares all received messages until message with value
           data is received or the timeout is reached"""
        resp = False
        if not alreadySearching:
            msg = self.search_for(msgID, data, in_database=in_database)
            if msg:
                resp = self._block_unless_found(msg.id, timeout)
            self.stopSearchingFor(msgID)
        else:
            resp = self._block_unless_found(msgID, timeout)

        return resp

    def search_for(self, msg_id, **kwargs):
        """Start queuing all data received with msg_id."""
        return self.__rx_thread.start_queuing(msg_id, **kwargs)

    def clear_msg_queues(self):
        """Clear all receive filters."""
        self.__rx_thread.clear_filters()

    def remove_msg_filter(self, msg_id):
        """Stop queuing received messages for a specific msg_id."""
        return self.__rx_thread.remove_filter(msg_id)

    def get_queued_data(self, msg_id):
        """Get data queued for msg_id."""

        resp = None
        resp = self.rxthread.getFirstRxMessage(msg_id)
        return resp

    def get_all_rx_messages(self, msgID=False):
        """ Returns all received messages """
        resp = None
        if self.receiving:
            resp = self.rxthread.getAllRxMessages(msgID)
        return resp

    def send_recv(self, tx_id, tx_data, rx_id, timeout=150, **kwargs):
        """Send a message and wait for a response."""
        resp = False
        # TODO: Finish
        self.start_queueing(rx_id, **kwargs)
        self.send_message(tx_id, tx_data, **kwargs)
        resp = self._block_unless_found(rx_id, timeout)
        return resp

    def print_periodics(self, info=False, search_for=''):
        """Print all periodic messages currently being sent."""
        if not self.sendingPeriodics:
            logging.info('No periodics currently being sent')
        if search_for:
            # pylint: disable=W0612
            (status, msgID) = self._checkMsgID(search_for)
            if not status:
                return False
            elif status == 1:  # searching periodics by id
                for periodic in self.currentPeriodics:
                    if periodic.id == msgID:
                        self.last_found_msg = periodic
                        self._print_msg(periodic)
                        for sig in periodic.signals:
                            self.last_found_sig = sig
                            self._print_sig(sig, value=True)
            else:  # searching by string or printing all
                found = False
                for msg in self.currentPeriodics:
                    if search_for.lower() in msg.name.lower():
                        found = True
                        self.last_found_msg = msg
                        self._print_msg(msg)
                        for sig in msg.signals:
                            self.last_found_sig = sig
                            self._print_sig(sig, value=True)
                    else:
                        msgPrinted = False
                        for sig in msg.signals:
                            #pylint: disable=E1103
                            short_name = (msgID.lower() in sig.name.lower())
                            full_name = (msgID.lower() in sig.full_name.lower())
                            #pylint: enable=E1103
                            if full_name or short_name:
                                found = True
                                if not msgPrinted:
                                    self.last_found_msg = msg
                                    self._print_msg(msg)
                                    msgPrinted = True
                                self.last_found_sig = sig
                                self._print_sig(sig, value=True)
                if not found:
                    logging.error(
                        'Unable to find a periodic message with that string!')
        else:
            for msg in self.currentPeriodics:
                self.last_found_msg = msg
                self._print_msg(msg)
                if info:
                    for sig in msg.signals:
                        self.last_found_sig = sig
                        self._print_sig(sig, value=True)
            if self.sendingPeriodics:
                print('Currently sending: '+str(len(self.currentPeriodics)))

    def _reverse(self, num, dlc):
        """Reverse the byte order of data."""
        out = ''
        if dlc > 0:
            out = num[:2]
        if dlc > 1:
            out = num[2:4] + out
        if dlc > 2:
            out = num[4:6] + out
        if dlc > 3:
            out = num[6:8] + out
        if dlc > 4:
            out = num[8:10] + out
        if dlc > 5:
            out = num[10:12] + out
        if dlc > 6:
            out = num[12:14] + out
        if dlc > 7:
            out = num[14:] + out
        return out

    def _check_type(self, msg_id, display=False):
        """Check for errors in a message id."""
        if not msg_id:
            raise ValueError('Invalid message ID {}'.format(msg_id))
        if isinstance(msg_id, str):
            try:
                # Check for a decimal string
                msg_id = int(msg_id)
            except ValueError:
                # Check for a hex string
                try:
                    msg_id = int(msg_id, 16)
                except ValueError:
                    # Not a number in a string, so process as text
                    pass
                else:
                    if msg_id < 0 or msg_id > 0xFFFFFFFF:
                        raise ValueError('Invalid message id {} - negative or too large!'.format(msg_id))
            else:
                if msg_id < 0 or msg_id > 0xFFFFFFFF:
                    raise ValueError('Invalid message id {} - negative or too large!'.format(msg_id))
        elif isinstance(msg_id, int) or isinstance(msg_id, long):
            if msg_id < 0 or msg_id > 0xFFFFFFFF:
                raise ValueError('Invalid message id {} - negative or too large!'.format(msg_id))
        else:
            raise TypeError('Expected str or int but got {}'.format(type(msg_id)))
        return msg_id

    def _get_message_obj(self, msg_id, data='', period=0, in_database=True):
        """Get the message object from the database or create one."""
        msg = None
        msg_id = self._check_type(msg_id)
        # Find the message id based on the input type
        if isinstance(msg_id, int) or isinstance(msg_id, long):
            # number
            if in_database:
                self.find_message(msg_id)
                if self.last_found_msg:
                    msg = self.last_found_msg
                    if data:
                        msg.set_data(data)
                else:
                    raise ValueError('Message ID: 0x{:X} not found in the'
                                     ' database!'.format(msg_id))
            else:
                data = data.replace(' ', '')
                dlc = (len(data) / 2) + (len(data) % 2)
                msg = DBCMessage(msg_id, 'Unknown', dlc)
                msg.period = period
        elif isinstance(msg_id, str):
            for message in self.imported.messages.values():
                if msg_id.lower() == message.name.lower():
                    msg = message
                    break
            else:
                raise ValueError('Message Name: {} not found in the'
                                 ' database!'.format(msg_id))
        return msg

    def _check_signal(self, signal, value=None, force=False):
        """Check the validity of a signal and optionally it's value.

        Returns the message object containing the updated signal on success.
        """
        if not self.imported:
            self.import_dbc()
        if not isinstance(signal, str):
            raise TypeError('Expected str but got {}'.format(type(signal)))
        # Grab the signal object by full or short name
        if signal.lower() not in self.imported.signals:
            if signal.lower() not in self.imported.signals_by_name:
                raise ValueError('Signal {} not found in the database!'
                                 ''.format(signal))
            else:
                sig = self.imported.signals_by_name[signal.lower()]
        else:
            sig = self.imported.signals[signal.lower()]
        logging.debug('Found signal {} - msg id {:X}'
                      ''.format(sig.name, sig.msg_id))
        # Grab the message this signal is transmitted from
        if sig.msg_id not in self.imported.messages:
            raise KeyError('Signal {} has no associated messages!'.format(signal))
        msg = self.imported.messages[sig.msg_id]
        if value:
            # Update the signal value
            sig.set_val(value, force=force)
        return msg

    def _print_msg(self, msg):
        """Print a colored CAN message."""
        print('')
        color = Style.BRIGHT + Fore.GREEN
        msgid = hex(msg.id)
        data = hex(msg.data)[2:]
        if msgid[-1] == 'L':
            msgid = msgid[:-1]
        if data[-1] == 'L':
            data = data[:-1]
        while len(data) < (msg.dlc * 2):
            data = '0' + data
        if msg.endianness != 0:
            data = self._reverse(data, msg.dlc)
        print('{}Message: {} - ID: {} - Data: 0x{}'.format(color, msg.name,
                                                           msgid, data))
        reset_color = Fore.RESET + Style.RESET_ALL
        node_color = Back.RESET + Fore.MAGENTA
        cycle_status = ' - Non-periodic'
        node = '{} - TX Node: {}{}'.format(node_color, msg.sender, reset_color)
        if msg.period != 0:
            sending = 'Not Sending'
            send_color = Fore.WHITE + Back.RED
            if msg.sending:
                sending = 'Sending'
                send_color = Fore.WHITE + Back.GREEN
            cycle = ' - Cycle time(ms): {}'.format(msg.period)
            status = ' - Status: {}{}'.format(send_color, sending)
            node = '{} - TX Node: {}{}'.format(node_color, msg.sender,
                                               reset_color)
            cycle_status = cycle + status
        print(cycle_status + node)

    def _print_sig(self, sig, short_name=False, value=False):
        """Print a colored CAN signal."""
        color = Fore.CYAN + Style.BRIGHT
        rst = Fore.RESET + Style.RESET_ALL
        if not short_name and not sig.full_name:
            short_name = True
        if short_name:
            name = sig.name
        else:
            name = sig.full_name
        print('{} - Signal: {}'.format(color, name))
        if sig.values.keys():
            if value:
                print('            ^- {}{}'.format(sig.get_val(), rst))
            else:
                print('            ^- [')
                multiple = False
                for key, val in sig.values.items():
                    if multiple:
                        print(', ')
                    print('{}({})'.format(key, hex(val)))
                    multiple = True
                print(']{}\n'.format(rst))
        else:
            if value:
                print('            ^- {}{}{}'.format(sig.get_val(), sig.units,
                                                     rst))
            else:
                print('            ^- [{} : {}]{}'.format(sig.min_val,
                                                          sig.max_val, rst))


class ReceiveThread(Thread):
    """Thread for receiving CAN messages."""

    def __init__(self, vxl, lock):
        """."""
        super().__init__()
        self.daemon = True
        # Protect all variables so locks can be used where needed
        self.__vxl = vxl
        self.__rx_lock = lock
        # This lock prevents queues from being removed from self.__msg_queues
        # between the check 'msg_id in self.__msg_queues' and getting
        # the item with self.__msg_queues[msg_id] which usually follows.
        # Adding/replacing a queue in self.__msg_queues is safe since a
        # reference will still exist when self.__msg_queues[msg_id] is called.
        self.__queue_lock = RLock()
        self.__stopped = Event()
        self.__log_path = ''
        self.__log_file = None
        self.__log_errors = False
        self.__log_request = Queue()
        self.__errors_found = False
        self.__msg_queues = {}
        self.__sleep_time = 0.1
        self.__bus_status = ''
        self.__tx_err_count = 0
        self.__rx_err_count = 0
        self.__time = None
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
            # TODO: look into why setNotification wasn't working and either
            #       remove or fix this.
            # WaitForSingleObject(self.msgEvent, 1)
            # Only modify the log file from the Thread
            elapsed += self.__sleep_time
            if elapsed >= 1:
                elapsed = 0
                for chan in self.__vxl.get_can_channels(True):
                    if chan not in self.__init_channels:
                        if self.__log_file is not None:
                            self.__stop_logging()
                        # TODO: Implement a way to pass this error to the
                        # main thread.
                        raise AssertionError('CAN case was connected or '
                                             'disconnected.')
            if self.__log_request == 'start':
                self.__start_logging()
            elif self.__log_request == 'stop':
                self.__stop_logging()

            if self.__msg_queues:
                # Requesting the chip state adds a message to the receive
                # queue. If the chip state is requested as fast as possible,
                # it will only add a message every 50ms. Since each received
                # message has a timestamp, this will give a worst case
                # resolution for self.get_time() of 50ms when no other CAN
                # traffic is being received.
                self.__vxl.request_chip_state()

            data = self.__receive()
            while data is not None:
                match = msg_start_pat.search(data)
                if not match:
                    logging.error('Received unknown frame format \'{}\'. '
                                  'Skipping...'.format(data))
                    data = self.__receive()
                    continue
                msg_type = match.group(1)
                channel = int(match.group(2)) + 1
                # Convert from nanoseconds to seconds
                time = int(match.group(3)) / 1000000000.0
                self.__time = time
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
                    error = error_pat.match(data)
                    if error:
                        self.__errors_found = True
                        if not self.__log_errors:
                            data = self.__receive()
                            continue
                        else:
                            raise NotImplementedError
                            # TODO: implement logging error frames
                            # data = self.__receive()
                            # continue
                    self.__errors_found = False
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
                        self.__enqueue_msg(time, msg_id, data)
                        if self.__log_file:
                            if msg_id > 0x7FF:
                                msg_id = '{:X}x'.format(msg_id & 0x1FFFFFFF)
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

    def __receive(self):
        """Receive incoming can frames."""
        self.__rx_lock.acquire()
        data = self.__vxl.receive()
        self.__rx_lock.release()
        return data

    def __start_logging(self):
        """Start logging all traffic."""
        self.__log_request = None
        file_opts = 'w+'
        # Append to the file if it already exists
        if path.isfile(self.__log_path):
            file_opts = 'a'
        self.__log_file = open(self.__log_path, file_opts)
        logging.info('Logging to: {}'.format(self.__log_path))
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

    def get_time(self):
        """Get the time of the last received CAN message.

        When messages are being queued, this time will be updated every 50ms
        even when no CAN messages are received.
        """
        return self.__time

    def start_queue(self, msg_id, max_size=1000):
        """Start queuing all data received for msg_id."""
        self.__msg_queues[msg_id] = Queue(max_size)
        self.__sleep_time = 0.01

    def stop_queue(self, msg_id):
        """Stop queuing received data for msg_id."""
        self.__queue_lock.acquire()
        if msg_id in self.__msg_queues:
            self.__msg_queues.pop(msg_id)
            if (not self.__msg_queues and not self.__log_request and
               not self.__log_path):
                self.__sleep_time = 0.1
        self.__queue_lock.release()

    def stop_all_queues(self):
        """Stop all queues."""
        self.__queue_lock.acquire()
        self.errors_found = False
        self.__msg_queues = {}
        if not self.__log_request and not self.__log_path:
            self.__sleep_time = 0.1
        self.__queue_lock.release()

    def __enqueue_msg(self, rx_time, msg_id, data):
        """Put a received message in the queue."""
        self.__queue_lock.acquire()
        if msg_id in self.__msg_queues:
            logging.debug('RX: {: >8X} {: <16}'.format(msg_id, data))
            if not self.__msg_queues[msg_id].full():
                self.__msg_queues[msg_id].put((rx_time, data))
            else:
                max_size = self.__msg_queues[msg_id].maxsize
                logging.error('Queue for 0x{:X} is full. {} wasn\'t added. The'
                              ' size is set to {}. Increase the size with the '
                              'max_size kwarg or remove messages more quickly.'
                              ''.format(msg_id, data, max_size))
        self.__queue_lock.release()

    def dequeue_msg(self, msg_id):
        """Get queued message data in the order it was received."""
        if msg_id in self.__msg_queues:
            if self.__msg_queues[msg_id].qsize():
                return self.__msg_queues[msg_id].get()
        else:
            logging.error('Queue for 0x{:X} hasn\'t been started! Call '
                          'start_queuing first.'.format(msg_id))
        return None


class TransmitThread(Thread):
    """Thread for transmitting CAN messages."""

    def __init__(self, vxl):
        """."""
        super(TransmitThread, self).__init__()
        self.daemon = True
        self.__vxl = vxl
        self.__stopped = Event()
        self.__messages = {}
        self.__elapsed = 0
        self.__sleep_time_ms = 1
        self.__sleep_time_s = 1
        self.__max_increment = 0

    def run(self):
        """The main loop for the thread."""
        while not self.__stopped.wait(self.__sleep_time_s):
            for msg in self.__messages.values():
                if self.__elapsed % msg.period == 0:
                    if msg.update_func is not None:
                        msg.set_data(msg.update_func(msg))
                    self.__vxl.send(msg.id, msg.get_data())
            if self.__elapsed >= self.__max_increment:
                self.__elapsed = self.__sleep_time_ms
            else:
                self.__elapsed += self.__sleep_time_ms

    def stop(self):
        """Stop the thread."""
        self.__stopped.set()

    def __update_times(self):
        """Update times for the transmit loop."""
        if len(self.__messages) == 1:
            msg = self.__messages.values()[0]
            self.__sleep_time_s = msg.period / 1000.0
            self.__max_increment = msg.period
            self.__sleep_time_ms = msg.period
        else:
            curr_gcd = self.__sleep_time_ms
            curr_lcm = self.__max_increment
            for i in range(1, len(self.__messages)):
                _, prev = self.__messages[i - 1]
                _, curr = self.__messages[i]
                tmp_gcd = gcd(prev, curr)
                tmp_lcm = prev * curr / tmp_gcd
                if curr_gcd is None or tmp_gcd < curr_gcd:
                    curr_gcd = tmp_gcd
                if tmp_lcm > curr_lcm:
                    curr_lcm = tmp_lcm
            self.__sleep_time_ms = curr_gcd
            self.__sleep_time_s = curr_gcd / 1000.0
            self.__max_increment = curr_lcm
        if self.__elapsed >= self.__max_increment:
            self.__elapsed = self.__sleep_time_ms

    def add(self, msg):
        """Add a periodic message to the thread."""
        self.__messages[msg.id] = msg
        self.__update_times()
        logging.debug('TX: {: >8X} {: <16} period={}ms'
                      ''.format(msg.id, msg.get_data(), msg.period))

    def remove(self, msg):
        """Remove a periodic message from the thread."""
        if msg.id in self.__messages:
            self.__messages.pop(msg.id)
            self.__update_times()
            logging.debug('Removed periodic message: 0x{:03X} {: <16} period='
                          '{}ms'.format(msg.id, msg.get_data(), msg.period))
        else:
            logging.error('{} (0x{:X}) is not being sent!'.format(msg.name,
                                                                  msg.id))
