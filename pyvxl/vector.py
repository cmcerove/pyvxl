#!/usr/bin/env python

"""Contains the CAN class for interacting with vector hardware."""

import traceback
import time
import logging
import os
import math
import sys
from os import path
from re import findall
from threading import Thread, Event, RLock
from ctypes import cdll, CDLL, c_uint, c_int, c_ubyte, c_ulong, cast
from ctypes import c_ushort, c_ulonglong, pointer, sizeof, POINTER
from ctypes import c_short, c_long, create_string_buffer
from binascii import unhexlify, hexlify
from fractions import gcd
from pyvxl import pydbc, settings, config
from pyvxl.vxl import VxlCan
from pyvxl.vector_data_types import event, driverConfig
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

    locks = []

    def __init__(self, channel=0, db_path=None, baud_rate=500000):
        """."""
        self.vxl = VxlCan(channel, baud_rate)
        self.vxl.start()
        self.db_path = db_path
        self.baud_rate = baud_rate
        self.drvConfig = None
        self.initialized = False
        self.imported = False
        self.sendingPeriodics = False
        self.lastFoundMessage = None
        self.lastFoundSignal = None
        self.lastFoundNode = None
        self.currentPeriodics = []
        self.receiving = False
        self.init_channel = 0
        self.channel = 0
        self.portHandle = c_long(-1)
        self.txthread = None
        self.stopTxThread = None
        self.parser = None
        self.stopRxThread = None
        self.rxthread = None
        self.validMsg = (None, None)
        if not self.locks:
            self.locks.append(RLock())

    def start_logging(self, path, *args, **kwargs):
        """Start logging."""
        if not self.initialized:
            logging.error('Initialization required to begin logging!')
            return False
        if not self.receiving:
            self.receiving = True
            self.stopRxThread = Event()
            self.rxthread = ReceiveThread(self.stopRxThread, self.portHandle,
                                          self.locks[0])
            path = self.rxthread.logTo(path, **kwargs)
            self.rxthread.start()
        else:
            path = self.rxthread.logTo(path, **kwargs)
        return path

    def stop_logging(self):
        """Stop logging."""
        result = False
        if self.receiving:
            result = True
            self.rxthread.stopLogging()
            if not self.rxthread.busy():
                self.stopRxThread.set()
                self.receiving = False
        else:
            logging.error('Not currently logging!')
        return result

    def import_db(self, db_path=None):
        """Import the database."""
        if db_path is not None:
            self.db_path = db_path
        elif self.db_path is None:
            raise ValueError('No database path specified!')
        if not isinstance(self.db_path, str):
            raise TypeError('Expected str but got {}'.format(type(db_path)))
        if not path.isfile(self.db_path):
            raise ValueError('Database {} does not exist'.format(db_path))

        dbcname = self.db_path.split('\\')[-1]
        try:
            self.parser = pydbc.importDBC(self.db_path)
            self.imported = True
            logging.info('Successfully imported: {}'.format(dbcname))
        except Exception:
            self.imported = False
            logging.error('Import failed!')
            logging.info('-' * 60)
            traceback.print_exc(file=sys.stdout)
            logging.info('-' * 60)
            raise

    def _send(self, msg, dataString, display=False):
        """Sends a spontaneous CAN message"""
        # Check endianness here and reverse if necessary
        txID = msg.id
        dlc = msg.dlc
        endianness = msg.endianness
        if endianness != 0: # Motorola(Big endian byte order) need to reverse
            dataString = self._reverse(dataString, dlc)

        if msg.update_func:
            dataString = unhexlify(msg.update_func(msg))
        else:
            dataString = unhexlify(dataString)

        if display:
            if dlc == 0:
                logging.info(
                        "Sending CAN Msg: 0x{0:X} Data: None".format(txID))
            else:
                logging.info(
                        "Sending CAN Msg: 0x{0:X} Data: {1}".format(txID & ~0x80000000,
                                                            hexlify(dataString).upper()))
        if dlc > 8:
            logging.error(
                'Sending of multiframe messages currently isn\'t supported!')
            return False
        else:
            xlEvent = event()
            data = create_string_buffer(dataString, 8)
            memset(pointer(xlEvent), 0, sizeof(xlEvent))
            xlEvent.tag = c_ubyte(0x0A)
            if txID > 0x8000:
                xlEvent.tagData.msg.id = c_ulong(txID | 0x80000000)
            else:
                xlEvent.tagData.msg.id = c_ulong(txID)
            xlEvent.tagData.msg.dlc = c_ushort(dlc)
            xlEvent.tagData.msg.flags = c_ushort(0)
            # Converting from a string to a c_ubyte array
            tmpPtr = pointer(data)
            dataPtr = cast(tmpPtr, POINTER(c_ubyte*8))
            xlEvent.tagData.msg.data = dataPtr.contents
            msgCount = c_uint(1)
            msgPtr = pointer(msgCount)
            eventPtr = pointer(xlEvent)
            #Send the CAN message
            transmitMsg(self.portHandle, self.channel, msgPtr,
                    eventPtr)

    def _send_periodic(self, msg, dataString, display=False):
        """Sends a periodic CAN message"""
        txID = msg.id
        dlc = msg.dlc
        period = msg.period
        endianness = msg.endianness
        if not self.initialized:
            logging.error(
                "Initialization required before a message can be sent!")
            return False
        if endianness != 0: # Motorola(Big endian byte order) need to reverse
            dataString = self._reverse(dataString, dlc)
        dataOrig = dataString
        if msg.update_func:
            dataString = unhexlify(msg.update_func(msg))
        else:
            dataString = unhexlify(dataOrig)
        if display:
            if dlc > 0:
                logging.info(
                    "Sending Periodic CAN Msg: 0x{0:X} Data: {1}".format(int(txID),
                                                                hexlify(dataString).upper()))
            else:
                logging.info(
                    "Sending Periodic CAN Msg: 0x{0:X} Data: None".format(int(txID)))
        dlc = len(dataString)
        data = create_string_buffer(dataString, 8)
        if not self.sendingPeriodics:
            self.stopTxThread = Event()
            self.txthread = TransmitThread(self.stopTxThread, self.channel,
                                           self.portHandle)
            self.sendingPeriodics = True
            self.txthread.add(txID, dlc, data, period, msg)
            self.txthread.start()
        else:
            self.txthread.add(txID, dlc, data, period, msg)
        self._send(msg, dataOrig, display=False)

    def start_periodics(self, node):
        """Starts all periodic messages except those transmitted by node"""
        if not self.imported:
            logging.error('Imported database required to start periodics!')
            return False
        if not self.parser.dbc.nodes.has_key(node.lower()):
            logging.error('Node not found in the database!')
            return False
        for periodic in self.parser.dbc.periodics:
            if not periodic.sender.lower() == node.lower():
                self.send_message(periodic.name)
        return True

    def stop_periodic(self, name):
        """Stops a periodic message
        @param name: signal name or message name or message id
        """
        if not self.initialized:
            logging.error(
                "Initialization required before a message can be sent!")
            return False
        if not name:
            logging.error('Input argument \'name\' is invalid')
            return False
        msgFound = None
        if self.sendingPeriodics:
            (status, msgID) = self._checkMsgID(name)
            if status == 0:  # invalid
                return False
            elif status == 1:  # number
                for msg in self.currentPeriodics:
                    if msgID == msg.id:
                        msgFound = msg
                        break
            else:  # string
                self.find_message(msgID, display=False)
                msg = None
                if self.lastFoundMessage:
                    msg = self.lastFoundMessage
                elif self._isValid(msgID, dis=False):
                    msg = self.validMsg[0]
                else:
                    logging.error('No messages or signals for that input!')
                    return False
                if msg in self.currentPeriodics:
                    msgFound = msg
            if msgFound:
                self.txthread.remove(msg.id)
                if msg.name != 'Unknown':
                    logging.info('Stopping Periodic Msg: ' + msg.name)
                else:
                    logging.info('Stopping Periodic Msg: ' + hex(msg.id)[2:])
                self.currentPeriodics.remove(msg)
                msg.sending = False
                if len(self.currentPeriodics) == 0:
                    self.stopTxThread.set()
                    self.sendingPeriodics = False
            else:
                logging.error('No periodic with that value to stop!')
                return False
            return True
        else:
            logging.error('No periodics to stop!')
            return False

    def stop_node(self, node):
        """Stop all periodic messages sent from a node
        @param node: the node to be stopped
        """
        if not self.sendingPeriodics:
            logging.error('No periodics to stop!')
        try:
            if type(node) == type(''):
                try: # test for decimal string
                    node = int(node)
                except ValueError:
                    node = int(node, 16)
        except ValueError:
            pass
        if isinstance(node, int):
            if node > 0xFFF:
                logging.error('Node value is too large!')
                return False
            self.find_node(node)
            if self.lastFoundNode:
                node = self.lastFoundNode.name
            else:
                logging.error('Invalid node number!')
                return False
        elif type(node) != type(''):
            logging.error('Invalid node type!')
            return False
        periodicsToRemove = []
        for msg in self.currentPeriodics:
            if msg.sender.lower() == node.lower(): #pylint: disable=E1103
                periodicsToRemove.append(msg.id)
        if not periodicsToRemove:
            logging.error('No periodics currently being sent by that node!')
            return False
        for msgid in periodicsToRemove:
            self.stop_periodic(msgid)
        return True

    def stop_periodics(self):
        """Stops all periodic messages currently being sent"""
        if self.sendingPeriodics:
            self.stopTxThread.set()
            self.sendingPeriodics = False
            for msg in self.currentPeriodics:
                msg.sending = False
            self.currentPeriodics = []
            logging.info('All periodics stopped')
            return True
        else:
            logging.warning('Periodics already stopped!')
            return False

    def send_message(self, msgID, data='', inDatabase=True, cycleTime=0,
                     display=True, sendOnce=False):
        """ Sends a complete spontaneous or periodic message changing all of
           the signal values """
        if not self.initialized:
            logging.error(
                'Initialization required before a message can be sent!')
            return False
        msg = None
        (status, msgID) = self._checkMsgID(msgID)
        if not status: # invalid error msg already printed
            return False
        elif status == 1: # number
            if inDatabase:
                self.find_message(msgID, display=False)
                if self.lastFoundMessage:
                    msg = self.lastFoundMessage
                else:
                    logging.error('Message not found!')
                    return False
            else:
                data = data.replace(' ', '')
                dlc = len(data)/2 if (len(data) % 2 == 0) else (len(data)+1)/2
                sender = ''
                if self.parser:
                    for node in self.parser.dbc.nodes.values():
                        if node.source_id == msgID & 0xFFF:
                            sender = node.name
                msg = pydbc.DBCMessage(msgID, 'Unknown', dlc, sender, [])
                msg.id = msgID
                msg.period = cycleTime
        else: # string
            for message in self.parser.dbc.messages.values():
                if msgID.lower() == message.name.lower():#pylint: disable=E1103
                    msg = message
                    break
            else:
                logging.error('Message ID: '+msgID+' - not found!')
                return False
        (dstatus, data) = self._checkMsgData(msg, data)
        if not dstatus:
            return False
        try:
            if msg.dlc > 0:
                msg.data = int(data, 16)
            else:
                msg.data = 0
            self._updateSignals(msg)
        except ValueError:
            logging.error('Non-hexadecimal characters found in message data')
            return False
        if msg.period == 0 or sendOnce:
            self._send(msg, data, display=display)
        else:
            if not msg.sending:
                msg.sending = True
                self.currentPeriodics.append(msg)
            self._send_periodic(msg, data, display=display)
        return True

    def send_signal(self, signal, value, force=False, display=True,
                    sendOnce=False):
        """Sends the CAN message containing signal with value"""
        if not self.initialized:
            logging.error(
                "Initialization required before a message can be sent!")
            return False
        if not signal or not value and value != 0:
            logging.error('Missing signal name or value!')
            return False
        if type(signal) != type(''):
            logging.error('Non-string signal name found!')
            return False
        if self._isValid(signal, value, force=force):
            msg = self.validMsg[0]
            value = self.validMsg[1]
            while len(value) < msg.dlc*2:
                value = '0'+value
            if msg.period == 0 or sendOnce:
                self._send(msg, value, display=display)
            else:
                if not msg.sending:
                    msg.sending = True
                    self.currentPeriodics.append(msg)
                self._send_periodic(msg, value, display=display)
            return True
        else:
            return False

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
        if not self.receiving:
            self.receiving = True
            self.stopRxThread = Event()
            self.rxthread = ReceiveThread(self.stopRxThread, self.portHandle,
                                          self.locks[0])
            self.rxthread.start()
        else:
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

        # If we started the rx thread, stop it now that we're done
        if not self.rxthread.busy():
            self.stopRxThread.set()
            self.receiving = False

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
        timeout = float(timeout)/1000.0

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
        if not self.receiving:
            self.receiving = True
            self.stopRxThread = Event()
            self.rxthread = ReceiveThread(self.stopRxThread, self.portHandle,
                                          self.locks[0])
            self.rxthread.search_for(msg.id, data, mask)
            self.rxthread.start()
        else:
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

    def print_config(self):
        """Prints the current hardware configuration"""
        if not self.initialized:
            logging.warning("Initialization required before hardware configuration can be printed")
            return False
        foundPiggy = False
        buff = create_string_buffer(32)
        printf("----------------------------------------------------------\n")
        printf("- %2d channels       Hardware Configuration              -\n",
               self.drvConfig.channelCount)
        printf("----------------------------------------------------------\n")
        for i in range(self.drvConfig.channelCount):
            sys.stdout.write('- Channel {},    '.format(math.pow(2, self.drvConfig.channel[i].channelIndex)))
            strncpy(buff, self.drvConfig.channel[i].name, 23)
            printf(" %23s, ", buff)
            memset(buff, 0, sizeof(buff))
            if self.drvConfig.channel[i].transceiverType != 0x0000:
                foundPiggy = True
                strncpy(buff, self.drvConfig.channel[i].transceiverName, 13)
                printf("%13s -\n", buff)
            else:
                printf("    no Cab!   -\n", buff)

        printf("----------------------------------------------------------\n")
        if not foundPiggy:
            logging.info("Virtual channels only!")
            return False

    def _get_message(self, msgID, data, inDatabase):
        """ Gets a message and data to be used for searching received messages
        """
        msg = None
        (status, msgID) = self._checkMsgID(msgID)
        if not status: # invalid - error msg already printed
            return (False, data)
        elif status == 1: # number
            if inDatabase:
                self.find_message(msgID, display=False)
                if self.lastFoundMessage:
                    msg = self.lastFoundMessage
                else:
                    logging.error(
                    'Message not found - use \'inDatabase=False\' to ignore')
                    return (False, data)
            else:
                if len(data) % 2 == 1:
                    logging.error('Odd length data found!')
                    return (False, data)
                dlc = len(data) / 2
                sender = ''
                for node in self.parser.dbc.nodes.values():
                    if node.source_id == msgID & 0xFFF:
                        sender = node.name
                msg = pydbc.DBCMessage(msgID, 'Unknown', dlc, sender, [])
                msg.id = msgID
                msg.period = 0
        else:  # string
            for message in self.parser.dbc.messages.values():
                if msgID.lower() == message.name.lower():#pylint: disable=E1103
                    msg = message
                    break
            else:
                logging.error('Message ID: '+msgID+' - not found!')
                return (False, data)
        chkData = data.replace('*', '0')
        (dstatus, chkData) = self._checkMsgData(msg, chkData)
        diffLen = len(chkData)-len(data)
        data = '0'*diffLen+data
        if not dstatus:
            return (False, data)
        return msg, data

    def _updateSignals(self, msg):
        """Updates the current signal values within message"""
        for sig in msg.signals:
            sig.val = msg.data&sig.mask

    def _checkMsgID(self, msgID, display=False):
        """Checks for errors in message ids"""
        caseNum = 0 # 0 - invalid, 1 - num, 2 - string
        if not msgID:
            caseNum = 0
            logging.error('Invalid message id - size 0!')
        elif type(msgID) == type(''):
            try: # check for decimal string
                msgID = int(msgID)
                caseNum = 1
            except ValueError: # check for hex string
                pass
            if not caseNum:
                try:
                    msgID = int(msgID, 16)
                    caseNum = 1
                except ValueError: # a non-number string
                    caseNum = 2
                    if not self.imported:
                        logging.error('No database currently imported!')
                        caseNum = 0
        elif isinstance(msgID, int):
            caseNum = 1
        else:
            caseNum = 0
            logging.error('Invalid message id - non-string and non-numeric!')
        if caseNum == 1:
            if (msgID > 0xFFFFFFFF) or (msgID < 0):
                caseNum = 0
                logging.error('Invalid message id - negative or too large!')
        return (caseNum, msgID)

    def _checkMsgData(self, msg, data):
        """Checks for errors in message data"""
        if type(data) == type(''):
            data = data.replace(' ', '')
            if data:
                try:
                    data = hex(int(data, 16))[2:]
                    data = data if data[-1] != 'L' else data[:-1]
                except ValueError:
                    logging.error('Non-hexadecimal digits found!')
                    return (False, data)
            if not data and msg.dlc > 0:
                data = hex(msg.data)[2:]
                data = data if data[-1] != 'L' else data[:-1]
            elif len(data) > msg.dlc*2:
                logging.error('Invalid message data - too long!')
                return (False, data)
            while len(data) < msg.dlc*2:
                data = '0'+data
            return (True, data)

        else:
            # TODO: possibly change this to support numeric data types
            logging.error('Invalid message data - found a number!')
            return (False, data)

    def _reverse(self, num, dlc):
        """Reverses the byte order of data"""
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

    def _isValid(self, signal, value=None, dis=True, force=False):
        """Checks the validity of a signal and optionally it's value"""
        if not self.imported:
            logging.warning('No CAN databases currently imported!')
            return False
        if not self.parser.dbc.signals.has_key(signal.lower()):
            if not self.parser.dbc.signalsByName.has_key(signal.lower()):
                if dis:
                    logging.error('Signal \'%s\' not found!'%signal)
                return False
            else:
                sig = self.parser.dbc.signalsByName[signal.lower()]
        else:
            sig = self.parser.dbc.signals[signal.lower()]
        if not self.parser.dbc.messages.has_key(sig.msg_id):
            logging.error('Message not found!')
            return False
        msg = self.parser.dbc.messages[sig.msg_id]
        if not self.parser.dbc.nodes.has_key(msg.sender.lower()):
            logging.error('Node not found!')
            return False
        if value == None:
            self.validMsg = (msg, 0)
            return True
        else:
            if sig.values.keys() and not force:
                if type(value) == type(''):
                    if sig.values.has_key(value.lower()):
                        value = sig.values[value]
                    else:
                        logging.error('Value \'%s\' not found for signal \'%s\'!', value, sig.full_name)
                        return False
                else:
                    try:
                        float(value)
                        if value not in sig.values.values():
                            logging.error('Value \'%s\' not found for signal \'%s\'!', value, sig.full_name)
                            return False
                    except ValueError:
                        logging.error('Invalid signal value type!')
                        return False
            elif force:
                try:
                    float(value)
                except ValueError:
                    logging.error('Unable to force a non numerical value!')
                    return False
            elif (float(value) < sig.min_val) or (float(value) > sig.max_val):
                logging.error('Value outside of range!')
                return False
            if not sig.set_val(value, force=force):
                logging.error('Unable to set the signal to that value!')
                return False
            # Clear the current value for the signal
            msg.data = msg.data&~sig.mask
            # Store the new value in the msg
            msg.data = msg.data|abs(sig.val)
            val = hex(msg.data)[2:]
            if val[-1] == 'L':
                val = val[:-1]
            self.validMsg = (msg, val)
            return True

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
                sys.stdout.write('            ^- [')
                multiple = False
                for key, val in sig.values.items():
                    if multiple:
                        sys.stdout.write(', ')
                    sys.stdout.write('{}({})'.format(key, hex(val)))
                    multiple = True
                sys.stdout.write(']{}\n'.format(rst))
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

    def __init__(self, stpevent, port_handle, lock):
        """."""
        super(ReceiveThread, self).__init__()
        self.daemon = True  # thread will die with the program
        self.stopped = stpevent
        self.portHandle = port_handle
        self.lock = lock
        flushRxQueue(port_handle)
        resetClock(port_handle)
        self.logging = False
        self.outfile = None
        self.errorsFound = False
        self.messagesToFind = {}
        self.outfile = None
        self.close_pending = False
        self.log_path = ''

    def run(self):
        """Main receive loop.

        When the receive queue empty, new messages are checked for every 10ms.
        When the receive queue has items, runs until all items are dequeued.
        """
        while not self.stopped.wait(0.01):
            # Blocks until a message is received or the timeout (ms) expires.
            # This event is passed to vxlApi via the setNotification function.
            # TODO: look into why setNotification isn't working and either
            #       remove or fix this.
            # WaitForSingleObject(self.msgEvent, 1)
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
                        # TODO: Figure out which part of the message determines
                        # absolute/relative
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
                        chan = str(int(math.pow(2, int(rxmsg[1][2:-1]))))
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

    def search_for(self, msgID, data, mask):
        """Sets the variables needed to wait for a CAN message"""
        self.messagesToFind[msgID] = MessageQueue(msgID, data, mask)
        return

    def stopSearchingFor(self, msgID):
        if self.messagesToFind:
            if msgID in self.messagesToFind:
                self.messagesToFind.pop(msgID)
            else:
                logging.error('Message ID not in the receive queue!')
        else:
            logging.error('No messages in the search queue!')
        return

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
        return

    def logTo(self, path, add_date=True):
        """Begins logging the CAN bus"""
        outpath = ''
        if not self.logging and path:
            tmstr = time.localtime()
            hr = tmstr.tm_hour
            hr = str(hr) if hr < 12 else str(hr-12)
            mn = str(tmstr.tm_min)
            sc = str(tmstr.tm_sec)
            mo = tmstr.tm_mon
            da = str(tmstr.tm_mday)
            wda = tmstr.tm_wday
            yr = str(tmstr.tm_year)
            if add_date:
                path = path+'['+hr+'-'+mn+'-'+sc+'].asc'
            file_opts = 'w+'
            if os.path.isfile(path):
                # append to the file
                file_opts = 'a'
            logging.info('Logging to: '+os.getcwd()+'\\'+path)
            for tries in range(5):
                try:
                    self.outfile = open(path, file_opts)
                except IOError:
                    time.sleep(0.2)
                else:
                    break
            else:
                # Failed for the last 5 times, try one more time and raise error
                self.outfile = open(path, file_opts)
            outpath = path
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                      'Sep', 'Oct', 'Nov', 'Dec']
            enddate = months[mo-1]+' '+da+' '+hr+':'+mn+':'+sc+' '+yr+'\n'
            dateLine = 'date '+days[wda]+' '+enddate
            lines = [dateLine, 'base hex  timestamps absolute\n',
                     'no internal events logged\n']
            self.outfile.writelines(lines)
            self.log_path = outpath
            self.logging = True
        return outpath

    def stopLogging(self):
        """Stop logging."""
        old_path = ''
        if self.logging:
            old_path = self.log_path
            try:
                self.outfile.flush()
                self.outfile.close()
            except IOError:
                self.close_pending = True
                logging.warning('Failed to close log file!')
            else:
                self.logging = False
        return old_path

    def busy(self):
        return bool(self.logging or self.messagesToFind)


class TransmitThread(Thread):
    """Thread for transmitting CAN messages."""

    def __init__(self, stpevent, channel, port_handle):
        """."""
        super(TransmitThread, self).__init__()
        self.daemon = True  # thread will die with the program
        self.messages = []
        self.channel = channel
        self.stopped = stpevent
        self.portHandle = port_handle
        self.elapsed = 0
        self.increment = 0
        self.currGcd = 0
        self.currLcm = 0

    def run(self):
        while not self.stopped.wait(self.currGcd):
            for msg in self.messages:
                if self.elapsed % msg[1] == 0:
                    if msg[2].update_func:
                        #msg[3](''.join(['{:02X}'.format(x) for x in msg[0][0].tagData.msg.data]))
                        data = unhexlify(msg[2].update_func(msg[2]))
                        data = create_string_buffer(data, len(data))
                        tmpPtr = pointer(data)
                        dataPtr = cast(tmpPtr, POINTER(c_ubyte*8))
                        msg[0][0].tagData.msg.data = dataPtr.contents
                    msgPtr = pointer(c_uint(1))
                    tempEvent = event()
                    eventPtr = pointer(tempEvent)
                    memcpy(eventPtr, msg[0], sizeof(tempEvent))
                    transmitMsg(self.portHandle, self.channel,
                                msgPtr,
                                eventPtr)
            if self.elapsed >= self.currLcm:
                self.elapsed = self.increment
            else:
                self.elapsed += self.increment

    def updateTimes(self):
        """Updates the GCD and LCM used in the run loop to ensure it's
           looping most efficiently"""
        if len(self.messages) == 1:
            self.currGcd = float(self.messages[0][1])/float(1000)
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

    def add(self, txID, dlc, data, cycleTime, message):
        """Adds a periodic message to the list of periodics being sent"""
        xlEvent = event()
        memset(pointer(xlEvent), 0, sizeof(xlEvent))
        xlEvent.tag = c_ubyte(0x0A)
        if txID > 0x8000:
            xlEvent.tagData.msg.id = c_ulong(txID | 0x80000000)
        else:
            xlEvent.tagData.msg.id = c_ulong(txID)
        xlEvent.tagData.msg.dlc = c_ushort(dlc)
        xlEvent.tagData.msg.flags = c_ushort(0)
        # Converting from a string to a c_ubyte array
        tmpPtr = pointer(data)
        dataPtr = cast(tmpPtr, POINTER(c_ubyte*8))
        xlEvent.tagData.msg.data = dataPtr.contents
        msgCount = c_uint(1)
        msgPtr = pointer(msgCount)
        eventPtr = pointer(xlEvent)
        for msg in self.messages:
            # If the message is already being sent, replace it with new data
            if msg[0].contents.tagData.msg.id == xlEvent.tagData.msg.id:
                msg[0] = eventPtr
                break
        else:
            self.messages.append([eventPtr, cycleTime, message])
        self.updateTimes()

    def remove(self, txID):
        """Removes a periodic from the list of currently sending periodics"""
        if txID > 0x8000:
            ID = txID | 0x80000000
        else:
            ID = txID
        for msg in self.messages:
            if msg[0].contents.tagData.msg.id == ID:
                self.messages.remove(msg)
                break
