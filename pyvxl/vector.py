#!/usr/bin/env python

"""Contains the CAN class for interacting with vector hardware."""

import traceback
import logging
from os import path
from sys import stdout
from re import findall
from time import localtime, sleep
from threading import Thread, Event, RLock, Condition
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
    rx_lock = None

    def __init__(self, channel=0, db_path=None, baud_rate=500000):
        """."""
        self.vxl = VxlCan(channel, baud_rate)
        self.vxl.start()
        self.__db_path = db_path
        if CAN.rx_lock is None:
            CAN.rx_lock = RLock()
        self.__tx_thread = TransmitThread(self.vxl)
        self.__tx_thread.start()
        self.__rx_thread = ReceiveThread(self.vxl, CAN.rx_lock)
        self.__rx_thread.start()
        self.__imported = None
        self.last_found_msg = None
        self.last_found_sig = None
        self.last_found_node = None
        # init()

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
        return self.rx_thread.start_logging(*args, **kwargs)

    def stop_logging(self):
        """Stop logging."""
        return self.rx_thread.stop_logging()

    def _send(self, msg, send_once=False):
        """Send a message."""
        if msg.update_func is not None:
            msg.set_data(msg.update_func(msg))
        self.vxl.send(msg.id, msg.get_data())
        if not send_once and msg.period:
            self.__tx_thread.add(msg)

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

    def send_all_messages_except(self, node):
        """Send all periodic messages except those transmitted by node."""
        self._check_node(node)
        for msg in self.imported.nodes[node.lower()].rx_messages:
            if msg.period:
                self._send(msg)

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
        numFound = 0
        for anode in self.parser.dbc.nodes.values():
            if status == 1:
                if node == anode.source_id:
                    numFound += 1
                    self.lastFoundNode = anode
            else:
                if node.lower() in anode.name.lower():#pylint: disable=E1103
                    numFound += 1
                    self.lastFoundNode = anode
                    if display:
                        txt = Fore.MAGENTA+Style.DIM+'Node: '+anode.name
                        txt2 = ' - ID: '+hex(anode.source_id)
                        print(txt+txt2+Fore.RESET+Style.RESET_ALL)
        if numFound == 0:
            self.lastFoundNode = None
            logging.info('No nodes found for that input')
        elif numFound > 1:
            self.lastFoundNode = None

    def find_message(self, search_str, display=False,
                     exact=True):#pylint: disable=R0912
        """Prints all messages of the dbc match 'search_str'"""
        if not self.imported:
            logging.error('No CAN databases currently imported!')
            return False
        numFound = 0
        (status, msgID) = self._checkMsgID(search_str)
        if status == 0: # invalid
            self.lastFoundMessage = None
            return False
        elif status == 1: # number
            try:
                if msgID > 0x8000:
                    #msgID = (msgID&~0xF0000FFF)|0x80000000
                    msgID |= 0x80000000
                    msg = self.parser.dbc.messages[msgID]
                else:
                    msg = self.parser.dbc.messages[msgID]
                numFound += 1
                self.lastFoundMessage = msg
                if display:
                    self._print_msg(msg)
                    for sig in msg.signals:
                        self._print_sig(sig)
            except KeyError:
                logging.error('Message ID 0x{:X} not found!'.format(msgID))
                self.lastFoundMessage = None
                return False
        else: # string
            for msg in self.parser.dbc.messages.values():
                if not exact:
                    if msgID.lower() in msg.name.lower():#pylint: disable=E1103
                        numFound += 1
                        self.lastFoundMessage = msg
                        if display:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
                else:
                    if msgID.lower() == msg.name.lower():#pylint: disable=E1103
                        numFound += 1
                        self.lastFoundMessage = msg
                        if display:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
        if numFound == 0:
            self.lastFoundMessage = None
            if display:
                logging.info('No messages found for that input')
        elif numFound > 1:
            self.lastFoundMessage = None
        return True

    def find_signal(self, search_str, display=False, exact=False):
        """Prints all signals of the dbc matching 'search_str'"""
        if not search_str or (type(search_str) != type('')):
            logging.error('No search string found!')
            return False
        if not self.imported:
            logging.warning('No CAN databases currently imported!')
            return False
        numFound = 0
        for msg in self.parser.dbc.messages.values():
            msgPrinted = False
            for sig in msg.signals:
                if not exact:
                    short_name = (search_str.lower() in sig.name.lower())
                    full_name = (search_str.lower() in sig.full_name.lower())
                else:
                    short_name = (search_str.lower() == sig.name.lower())
                    full_name = (search_str.lower() == sig.full_name.lower())
                if full_name or short_name:
                    numFound += 1
                    self.lastFoundSignal = sig
                    self.lastFoundMessage = msg
                    if display:
                        if not msgPrinted:
                            self._print_msg(msg)
                            msgPrinted = True
                        self._print_sig(sig)
        if numFound == 0:
            self.lastFoundSignal = None
            logging.info('No signals found for that input')
        elif numFound > 1:
            self.lastFoundSignal = None
        return True

    def get_message(self, search_str):
        """ Returns the message object associated with search_str """
        ret = None
        if self.find_message(search_str, exact=True) and self.lastFoundMessage:
            ret = self.lastFoundMessage
        return ret

    def get_signals(self, search_str):
        """ Returns a list of signals objects associated with message search_str

        search_str (string): the message name whose signals will be returned
        """
        ret = None
        if self.find_message(search_str, exact=True) and self.lastFoundMessage:
            ret = self.lastFoundMessage.signals
        return ret

    def get_signal_values(self, search_str):
        """ Returns a dictionary of values associated with signal search_str

        search_str (string): the signal name whose values will be returned
        """
        ret = None
        if self.find_signal(search_str, exact=True) and self.lastFoundSignal:
            ret = self.lastFoundSignal.values
        return ret

    def wait_for_no_error(self, timeout=0):
        """ Blocks until the CAN bus comes out of an error state """
        errors_found = True
        if not self.receiving:
            self.receiving = True
            self.stopRxThread = Event()
            self.rxthread = ReceiveThread(self.stopRxThread, self.portHandle,
                                          self.locks[0])
            self.rxthread.start()

        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while self.rxthread.errorsFound:
                time.sleep(0.001)
            errors_found = False
        else:
            startTime = time.clock()
            timeout = float(timeout) / 1000.0
            while (time.clock() - startTime) < timeout:
                if not self.rxthread.errorsFound:
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
        self.rxthread.errorsFound = False

        if flush:
            flushRxQueue(self.portHandle)

        if not timeout:
            # Wait as long as necessary if there isn't a timeout set
            while not self.rxthread.errorsFound:
                time.sleep(0.001)
            errors_found = True
        else:
            startTime = time.clock()
            timeout = float(timeout) / 1000.0
            while (time.clock() - startTime) < timeout:
                if self.rxthread.errorsFound:
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
            self.rxthread.errorsFound = False
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
                 inDatabase=True):
        """Compares all received messages until message with value
           data is received or the timeout is reached"""
        resp = False
        if not alreadySearching:
            msg = self.search_for(msgID, data, inDatabase=inDatabase)
            if msg:
                resp = self._block_unless_found(msg.id, timeout)
            self.stopSearchingFor(msgID)
        else:
            resp = self._block_unless_found(msgID, timeout)

        return resp

    def search_for(self, msgID, data, inDatabase=True):
        """Adds a message to the search queue in the receive thread"""
        if not self.initialized:
            logging.error(
                'Initialization required before messages can be received!')
            return False
        msg, data = self._get_message(msgID, data, inDatabase)
        if not msg:
            return False
        mask = ''
        if data:
            tmpData = []
            mask = []
            for x in range(len(data)):
                if data[x] == '*':
                    tmpData.append('0')
                    mask.append('0000')
                else:
                    tmpData.append(data[x])
                    mask.append('1111')
            mask = ''.join(mask)
            mask = int(mask, 2)
            data = int(''.join(tmpData), 16)
        self.rxthread.search_for(msg.id, data, mask)

        return msg

    def clear_search_queue(self):
        """ Clears the received message queue """
        resp = False
        if self.receiving:
            self.rxthread.clearSearchQueue()
            resp = True
        return resp

    def stop_searching_for(self, msgID, inDatabase=True):
        """ Removes a message from the search queue """
        resp = False
        if self.receiving:
            msg, data = self._get_message(msgID, '', inDatabase)
            if msg:
                self.rxthread.stopSearchingFor(msg.id)
        return resp

    def get_first_rx_message(self, msgID=False):
        """ Returns the first received message """
        resp = None
        if self.receiving:
            resp = self.rxthread.getFirstRxMessage(msgID)
        return resp

    def get_all_rx_messages(self, msgID=False):
        """ Returns all received messages """
        resp = None
        if self.receiving:
            resp = self.rxthread.getAllRxMessages(msgID)
        return resp

    def send_diag(self, sendID, sendData, respID, respData='',
                  inDatabase=True, timeout=150):
        """Sends a diagnotistic message and returns the response"""
        resp = False
        msg = self.search_for(respID, respData, inDatabase=inDatabase)
        if msg:
            self.send_message(sendID, sendData, inDatabase=inDatabase)
            resp = self._block_unless_found(msg.id, timeout)
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
                        self.lastFoundMessage = periodic
                        self._print_msg(periodic)
                        for sig in periodic.signals:
                            self.lastFoundSignal = sig
                            self._print_sig(sig, value=True)
            else:  # searching by string or printing all
                found = False
                for msg in self.currentPeriodics:
                    if search_for.lower() in msg.name.lower():
                        found = True
                        self.lastFoundMessage = msg
                        self._print_msg(msg)
                        for sig in msg.signals:
                            self.lastFoundSignal = sig
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
                                    self.lastFoundMessage = msg
                                    self._print_msg(msg)
                                    msgPrinted = True
                                self.lastFoundSignal = sig
                                self._print_sig(sig, value=True)
                if not found:
                    logging.error(
                        'Unable to find a periodic message with that string!')
        else:
            for msg in self.currentPeriodics:
                self.lastFoundMessage = msg
                self._print_msg(msg)
                if info:
                    for sig in msg.signals:
                        self.lastFoundSignal = sig
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
            for message in self.parser.dbc.messages.values():
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
        if signal.lower() not in self.parser.dbc.signals:
            if signal.lower() not in self.parser.dbc.signalsByName:
                raise ValueError('Signal {} not found in the database!'
                                 ''.format(signal))
            else:
                sig = self.parser.dbc.signalsByName[signal.lower()]
        else:
            sig = self.parser.dbc.signals[signal.lower()]
        logging.debug('Found signal {} - msg id {:X}'
                      ''.format(sig.name, sig.msg_id))
        # Grab the message this signal is transmitted from
        if sig.msg_id not in self.parser.dbc.messages:
            raise KeyError('Signal {} has no associated messages!'.format(signal))
        msg = self.parser.dbc.messages[sig.msg_id]
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


class MessageQueue(object):
    """Holds a queue of received data for a single message."""

    def __init__(self, msg_id, data, mask):
        """."""
        self.msg_id = msg_id
        self.data = data
        self.mask = mask
        self.rxFrames = []

    def get_first_msg(self):
        """Get the first received message."""
        resp = None
        if self.rxFrames:
            resp = self.rxFrames[0]
            self.rxFrames = self.rxFrames[1:]
        return resp

    def get_all_msgs(self):
        """Get all received messages."""
        # Copy the list so we don't return the erased version
        resp = list(self.rxFrames)
        self.rxFrames = []
        return resp


class ReceiveThread(Thread):
    """Thread for receiving CAN messages."""

    def __init__(self, vxl, lock):
        """."""
        super(ReceiveThread, self).__init__()
        self.daemon = True
        self.vxl = vxl
        self.__stopped = Event()
        self.lock = lock
        self.logging = False
        self.outfile = None
        self.errorsFound = False
        self.messagesToFind = {}
        self.outfile = None
        self.close_pending = False
        self.log_path = ''
        self.sleep_time = 1

    def run(self):
        """Main receive loop.

        When the receive queue empty, new messages are checked for every 10ms.
        When the receive queue has items, runs until all items are dequeued.
        """
        while not self.__stopped.wait(self.sleep_time):
            # print('RX main loop - event.is_set() ={}'.format(self.__stopped.is_set()))
            # Blocks until a message is received or the timeout (ms) expires.
            # This event is passed to vxlApi via the setNotification function.
            # TODO: look into why setNotification isn't working and either
            #       remove or fix this.
            # WaitForSingleObject(self.msgEvent, 1)
            data = self.vxl.receive()
            """
            msg = c_uint(1)
            self.msgPtr = pointer(msg)
            status = 0
            received = False
            rxMsgs = []
            while not status:
                rxEvent = event()
                rxEventPtr = pointer(rxEvent)
                self.lock.acquire()
                status = receiveMsg(self.portHandle, self.msgPtr,
                                    rxEventPtr)
                error_status = str(getError(status))
                rxmsg = ''.join(getEventStr(rxEventPtr)).split()
                self.lock.release()
                messagesToFind = dict(self.messagesToFind)
                if error_status == 'XL_SUCCESS':
                    received = True
                    noError = 'error' not in rxmsg[4].lower()
                    if not noError:
                        self.errorsFound = True
                    else:
                        self.errorsFound = False

                    if noError and 'chip' not in rxmsg[0].lower():
                        # print(' '.join(rxmsg))
                        tstamp = float(rxmsg[2][2:-1])
                        tstamp = str(tstamp/1000000000.0).split('.')
                        decVals = tstamp[1][:6]+((7-len(tstamp[1][:6]))*' ')
                        tstamp = ((4-len(tstamp[0]))*' ')+tstamp[0]+'.'+decVals
                        msgid = rxmsg[3][3:]
                        if len(msgid) > 4:
                            try:
                                msgid = hex(int(msgid, 16)&0x1FFFFFFF)[2:-1]+'x'
                            except ValueError:
                                print(' '.join(rxmsg))
                        msgid = msgid+((16-len(msgid))*' ')
                        dlc = rxmsg[4][2]+' '
                        io = 'Rx   d'
                        if int(dlc) > 0:
                            if rxmsg[6].lower() == 'tx':
                                io = 'Tx   d'
                        data = ''
                        if int(dlc) > 0:
                            data = ' '.join(findall('..?', rxmsg[5]))
                        data += '\n'
                        chan = str(int(2 ** int(rxmsg[1][2:-1])))
                        rxMsgs.append(tstamp+' '+chan+' '+msgid+io+dlc+data)
                        if messagesToFind:
                            msgid = int(rxmsg[3][3:], 16)
                            if msgid > 0xFFF:
                                msgid = msgid&0x1FFFFFFF
                            data = ''.join(findall('..?', rxmsg[5]))

                            # Is the received message one we're looking for?
                            if msgid in messagesToFind:
                                fndMsg = ''.join(findall('[0-9A-F][0-9A-F]?',
                                                         rxmsg[5]))
                                txt = 'Received CAN Msg: '+hex(msgid)
                                logging.info(txt+' Data: '+fndMsg)
                                storeMsg = False
                                # Are we also looking for specific data?
                                searchData = messagesToFind[msgid].data
                                mask = messagesToFind[msgid].mask
                                if searchData:
                                    try:
                                        data = int(data, 16) & mask
                                        if data == searchData:
                                            storeMsg = True
                                    except ValueError:
                                        pass
                                else:
                                    storeMsg = True

                                if storeMsg:
                                    messagesToFind[msgid].rxFrames.append(fndMsg)
                elif error_status != 'XL_ERR_QUEUE_IS_EMPTY':
                    logging.error(error_status)
                elif received:
                    if self.logging:
                        if not self.outfile.closed:
                            self.outfile.writelines(rxMsgs)
                            self.outfile.flush()
                            if self.close_pending:
                                self.logging = False
                                self.close_pending = False
                                try:
                                    self.outfile.close()
                                except IOError:
                                    logging.warning('Failed to close log file!')
            if self.logging:
                if not self.outfile.closed:
                    self.outfile.flush()
                    if self.close_pending:
                        self.logging = False
                        self.close_pending = False
                        try:
                            self.outfile.close()
                        except IOError:
                            logging.warning('Failed to close log file!')
        if self.logging:
            if not self.outfile.closed:
                self.outfile.flush()
                try:
                    self.outfile.close()
                except IOError:
                    logging.warning('Failed to close log file!')
        """

    def search_for(self, msgID, data, mask):
        """Sets the variables needed to wait for a CAN message"""
        self.messagesToFind[msgID] = MessageQueue(msgID, data, mask)
        self.sleep_time = 0.01

    def stopSearchingFor(self, msgID):
        """Stop searching for a message."""
        if self.messagesToFind:
            if msgID in self.messagesToFind:
                self.messagesToFind.pop(msgID)
                if not self.messagesToFind and not self.logging:
                    self.sleep_time = 1
            else:
                logging.error('Message ID not in the receive queue!')
        else:
            logging.error('No messages in the search queue!')

    def _getRxMessages(self, msgID, single=False):
        resp = None
        if msgID in self.messagesToFind:
            if single:
                resp = self.messagesToFind[msgID].get_first_msg()
            else:
                resp = self.messagesToFind[msgID].get_all_msgs()
        return resp

    def getFirstRxMessage(self, msgID):
        """Removes the first received message and returns it"""
        return self._getRxMessages(msgID, single=True)

    def getAllRxMessages(self, msgID):
        """Removes all received messages and returns them"""
        return self._getRxMessages(msgID)

    def clearSearchQueue(self):
        self.errorsFound = False
        self.messagesToFind = {}
        if not self.logging:
            self.sleep_time = 1

    def start_logging(self, log_path, add_date=True):
        """Start logging all traffic."""
        if self.logging:
            raise AssertionError('Already logging to {}. Call stop_logging '
                                 'before starting a new log.'
                                 ''.format(self.log_path))
        if not isinstance(log_path, str):
            raise TypeError('Expected str but got {}'.format(type(log_path)))
        directory, _ = path.split(log_path)
        if directory and not path.isdir(directory):
            raise ValueError('{} is not a valid directory!'.format(directory))
        tmstr = localtime()
        hr = tmstr.tm_hour % 12
        mn = tmstr.tm_min
        sc = tmstr.tm_sec
        mo = tmstr.tm_mon - 1
        da = tmstr.tm_mday
        wda = tmstr.tm_wday
        yr = tmstr.tm_year
        if add_date:
            log_path = '{}[{}-{}-{}].asc'.format(log_path, hr, mn, sc)
        file_opts = 'w+'
        if path.isfile(log_path):
            # append to the file
            file_opts = 'a'
        for tries in range(5):
            try:
                self.outfile = open(log_path, file_opts)
            except IOError:
                sleep(0.2)
            else:
                break
        else:
            # Failed for the last 5 times, try one more time and raise error
            self.outfile = open(log_path, file_opts)
        self.log_path = path.abspath(log_path)
        logging.info('Logging to: {}'.format(self.log_path))
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                  'Sep', 'Oct', 'Nov', 'Dec']
        data_str = 'date {} {} {} {}:{}:{} {}\n'
        self.outfile.write(data_str.format(days[wda], months[mo], da, hr, mn,
                                           sc, yr))
        self.outfile.write('base hex  timestamps absolute\n')
        self.outfile.write('no internal events logged\n')
        self.logging = True
        self.sleep_time = 0.01
        return self.log_path

    def stop_logging(self):
        """Stop logging."""
        old_path = ''
        if self.logging:
            old_path = self.log_path
            try:
                self.outfile.flush()
                self.outfile.close()
            except IOError:
                self.close_pending = True
                logging.error('Failed closing the log file!')
            else:
                if not self.messagesToFind:
                    self.sleep_time = 1
                self.logging = False
        return old_path


class TransmitThread(Thread):
    """Thread for transmitting CAN messages."""

    def __init__(self, vxl):
        """."""
        super(TransmitThread, self).__init__()
        self.daemon = True
        self.vxl = vxl
        self.__stopped = Event()
        self.lock = RLock()
        self.messages = {}
        self.elapsed = 0
        self.increment = 0
        self.currGcd = 1
        self.currLcm = 0

    def run(self):
        """The main loop for the thread."""
        while not self.__stopped.wait(self.currGcd):
            # print('TX main loop - event.is_set() ={}'.format(self.__stopped.is_set()))
            pass
            """
            self.lock.acquire()
            for msg in self.tx_list[index]:
                if msg.update_func:
                    msg.set_data(unhexlify(msg[2].update_func(msg[2])))
            self.lock.release()

            for msg in self.messages:
                if self.elapsed % msg[1] == 0:
                    if msg[2].update_func:
                        data = unhexlify(msg[2].update_func(msg[2]))
                        '''
                        data = create_string_buffer(data, len(data))
                        tmpPtr = pointer(data)
                        dataPtr = cast(tmpPtr, POINTER(c_ubyte*8))
                        msg[0][0].tagData.msg.data = dataPtr.contents
                        '''
                    else:
                        tx_msgs.append((msg.id, msg.get_data()))
                    '''
                    msgPtr = pointer(c_uint(1))
                    tempEvent = event()
                    eventPtr = pointer(tempEvent)
                    memcpy(eventPtr, msg[0], sizeof(tempEvent))
                    transmitMsg(self.portHandle, self.channel,
                                msgPtr,
                                eventPtr)
                    '''
            if self.elapsed >= self.currLcm:
                self.elapsed = self.increment
            else:
                self.elapsed += self.increment
            """

    def update_tx_lists(self):
        """Updates the GCD and LCM used in the run loop to ensure it's
           looping most efficiently"""
        self.lock.acquire()
        if len(self.messages) == 1:
            self.currGcd = float(self.messages[0][1]) / 1000.0
            self.currLcm = self.elapsed = self.increment = self.messages[0][1]
        else:
            cGcd = self.increment
            cLcm = self.currLcm
            for i in range(len(self.messages)-1):
                tmpGcd = gcd(self.messages[i][1], self.messages[i+1][1])
                tmpLcm = (self.messages[i][1]*self.messages[i+1][1])/tmpGcd
                if tmpGcd < cGcd:
                    cGcd = tmpGcd
                if tmpLcm > cLcm:
                    cLcm = tmpLcm
            self.increment = cGcd
            self.currGcd = float(cGcd)/float(1000)
            self.currLcm = cLcm
        self.lock.release()

    def add(self, msg):
        """Add a periodic message to the thread."""
        self.messages[msg.id] = msg
        self.update_tx_lists()

    def remove(self, msg):
        """Remove a periodic message from the thread."""
        if msg.id in self.messages:
            self.messages.pop(msg.id)
            self.update_tx_lists()
        else:
            logging.error('{} (0x{:X}) is not being sent!'.format(msg.name,
                                                                  msg.id))
