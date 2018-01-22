#!/usr/bin/env python

"""Contains the CAN class for interacting with vector hardware."""

# pylint: disable=W0223, R0911, C0103
import traceback
import time
import logging
import os
import sys
import inspect
import socket
import select
import shlex
from argparse import ArgumentParser
from threading import Event
from binascii import unhexlify, hexlify
from types import IntType, LongType
from pyvxl import pydbc, settings, config
from pyvxl.vxl import VxlCan
from colorama import init, deinit, Fore, Back, Style

__program__ = 'can'


class CAN(object):
    """Class to manage Vector hardware"""
    def __init__(self, channel, dbc_path, baudrate):
        self.dbc_path = dbc_path
        self.vxl = VxlCan(channel, baudrate)
        self.baudrate = baudrate
        self.status = c_short(0)
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
        self.set_channel(channel)
        self.portHandle = c_long(-1)
        self.txthread = None
        self.stopTxThread = None
        self.parser = None
        self.stopRxThread = None
        self.rxthread = None
        self.validMsg = (None, None)

    def set_channel(self, channel):
        """Sets the vector hardware channel."""
        self.init_channel = int(channel)
        self.channel = c_ulonglong(1 << (self.init_channel - 1))

    def start(self, display=False):
        """Initializes and connects to a CAN channel."""
        init()  # Initialize colorama
        return self.vxl.start()

    def stop(self):
        """Cleanly disconnects from the CANpiggy"""
        deinit()
        if self.initialized:
            if self.sendingPeriodics:
                self.stop_periodics()
            if self.receiving:
                self.receiving = False
                self.stopRxThread.set()
            self.vxl.stop()
        return True

    def _send_periodic(self, msg, dataString, display=False):
        """Sends a periodic CAN message"""
        if not self.initialized:
            logging.error(
                "Initialization required before a message can be sent!")
            return False

        txID = msg.txId
        dlc = msg.dlc
        period = msg.cycleTime
        endianness = msg.endianness
        if endianness != 0: # Motorola(Big endian byte order) need to reverse
            dataString = self._reverse(dataString, dlc)

        dataOrig = dataString
        if msg.updateFunc:
            dataString = unhexlify(msg.updateFunc(msg))
        else:
            dataString = unhexlify(dataOrig)
        if display:
            if dlc > 0:
                logging.info("Sending Periodic CAN Msg: 0x{0:X} Data: {1}".format(int(txID),
                             hexlify(dataString).upper()))
            else:
                logging.info("Sending Periodic CAN Msg: 0x{0:X} Data: None".format(int(txID)))
        dlc = len(dataString)
        data = create_string_buffer(dataString, 8)
        if not self.sendingPeriodics:
            self.stopTxThread = Event()
            self.txthread = transmitThread(self.stopTxThread, self.channel,
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
                data = hex(periodic.initData)[2:]
                if data[-1] == 'L':
                    data = data[:-1]
                self.send_message(periodic.name, data)
        return True

    def stop_periodic(self, name):  # pylint: disable=R0912
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
                    if msgID == msg.txId:
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
                self.txthread.remove(msg.txId)
                if msg.name != 'Unknown':
                    logging.info('Stopping Periodic Msg: ' + msg.name)
                else:
                    logging.info('Stopping Periodic Msg: ' + hex(msg.txId)[2:])
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

    def stop_node(self, node):  #pylint: disable=R0912
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
        if type(node) == IntType:
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
                periodicsToRemove.append(msg.txId)
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

    def import_dbc(self):
        """ Imports the selected dbc """
        dbcname = self.dbc_path.split('\\')[-1]
        if not os.path.exists(self.dbc_path):
            logging.error('Path: \'{0}\' does not exist!'.format(self.dbc_path))
            return False
        try:
            self.parser = pydbc.importDBC(self.dbc_path)
            self.imported = True
            logging.info('Successfully imported: '+dbcname)
            return True
        except Exception: #pylint: disable=W0703
            self.imported = False
            logging.error('Import failed!')
            print '-' * 60
            traceback.print_exc(file=sys.stdout)
            print '-' * 60
            return False

    #pylint: disable=R0912
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
                        if node.sourceID == msgID&0xFFF:
                            sender = node.name
                msg = pydbc.DBCMessage(msgID, 'Unknown', dlc, sender, [], None,
                                       None, None)
                msg.txId = msgID
                msg.cycleTime = cycleTime
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
        if msg.cycleTime == 0 or sendOnce:
            self._send(msg, data, display=display)
        else:
            if not msg.sending:
                msg.sending = True
                self.currentPeriodics.append(msg)
            self._send_periodic(msg, data, display=display)
        return True

    #pylint: enable=R0912
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
            if msg.cycleTime == 0 or sendOnce:
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
                if node == anode.sourceID:
                    numFound += 1
                    self.lastFoundNode = anode
            else:
                if node.lower() in anode.name.lower():#pylint: disable=E1103
                    numFound += 1
                    self.lastFoundNode = anode
                    if display:
                        txt = Fore.MAGENTA+Style.DIM+'Node: '+anode.name
                        txt2 = ' - ID: '+hex(anode.sourceID)
                        print txt+txt2+Fore.RESET+Style.RESET_ALL
        if numFound == 0:
            self.lastFoundNode = None
            logging.info('No nodes found for that input')
        elif numFound > 1:
            self.lastFoundNode = None

    def find_message(self, searchStr, display=False,
                     exact=True):#pylint: disable=R0912
        """Prints all messages of the dbc match 'searchStr'"""
        if not self.imported:
            logging.error('No CAN databases currently imported!')
            return False
        numFound = 0
        (status, msgID) = self._checkMsgID(searchStr)
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
                    self._printMessage(msg)
                    for sig in msg.signals:
                        self._printSignal(sig)
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
                            self._printMessage(msg)
                            for sig in msg.signals:
                                self._printSignal(sig)
                else:
                    if msgID.lower() == msg.name.lower():#pylint: disable=E1103
                        numFound += 1
                        self.lastFoundMessage = msg
                        if display:
                            self._printMessage(msg)
                            for sig in msg.signals:
                                self._printSignal(sig)
        if numFound == 0:
            self.lastFoundMessage = None
            if display:
                logging.info('No messages found for that input')
        elif numFound > 1:
            self.lastFoundMessage = None
        return True

    def find_signal(self, searchStr, display=False, exact=False):
        """Prints all signals of the dbc matching 'searchStr'"""
        if not searchStr or (type(searchStr) != type('')):
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
                    shortName = (searchStr.lower() in sig.name.lower())
                    fullName = (searchStr.lower() in sig.fullName.lower())
                else:
                    shortName = (searchStr.lower() == sig.name.lower())
                    fullName = (searchStr.lower() == sig.fullName.lower())
                if fullName or shortName:
                    numFound += 1
                    self.lastFoundSignal = sig
                    self.lastFoundMessage = msg
                    if display:
                        if not msgPrinted:
                            self._printMessage(msg)
                            msgPrinted = True
                        self._printSignal(sig)
        if numFound == 0:
            self.lastFoundSignal = None
            logging.info('No signals found for that input')
        elif numFound > 1:
            self.lastFoundSignal = None
        return True

    def get_message(self, searchStr):
        """ Returns the message object associated with searchStr """
        ret = None
        if self.find_message(searchStr, exact=True) and self.lastFoundMessage:
            ret = self.lastFoundMessage
        return ret

    def get_signals(self, searchStr):
        """ Returns a list of signals objects associated with message searchStr

        searchStr (string): the message name whose signals will be returned
        """
        ret = None
        if self.find_message(searchStr, exact=True) and self.lastFoundMessage:
            ret = self.lastFoundMessage.signals
        return ret

    def get_signal_values(self, searchStr):
        """ Returns a dictionary of values associated with signal searchStr

        searchStr (string): the signal name whose values will be returned
        """
        ret = None
        if self.find_signal(searchStr, exact=True) and self.lastFoundSignal:
            ret = self.lastFoundSignal.values
        return ret

    def wait_for_error(self):
        """ Blocks until the CAN bus goes into an error state """
        if not self.receiving:
            self.receiving = True
            self.stopRxThread = Event()
            msgEvent = CreateEvent(None, 0, 0, None)
            msgPointer = pointer(c_int(msgEvent.handle))
            self.status = setNotification(self.portHandle, msgPointer, 1)
            self._printStatus('Set Notification')
            self.rxthread = receiveThread(self.stopRxThread, self.portHandle,
                                          msgEvent)
            self.rxthread.start()

        while not self.rxthread.errorsFound:
            time.sleep(0.001)

        if not self.rxthread.busy():
            self.stopRxThread.set()
            self.receiving = False

        self.stop_periodics()
        self.vxl.reconnect()
        return

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
    # pylint: disable=R0912, R0914
    def wait_for(self, msgID, data, timeout, alreadySearching=False,
                 inDatabase=True):
        """Compares all received messages until message with value
           data is received or the timeout is reached"""
        resp = False
        if not alreadySearching:
            msg = self.search_for(msgID, data, inDatabase=inDatabase)
            if msg:
                resp = self._block_unless_found(msg.txId, timeout)
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
            msgEvent = CreateEvent(None, 0, 0, None)
            msgPointer = pointer(c_int(msgEvent.handle))
            self.status = setNotification(self.portHandle, msgPointer, 1)
            self._printStatus('Set Notification')
            self.rxthread = receiveThread(self.stopRxThread, self.portHandle,
                                          msgEvent)
            self.rxthread.searchFor(msg.txId, data, mask)
            self.rxthread.start()
        else:
            self.rxthread.searchFor(msg.txId, data, mask)

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
                self.rxthread.stopSearchingFor(msg.txId)
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
    # pylint: enable=R0912, R0914
    def send_diag(self, sendID, sendData, respID, respData='',
                  inDatabase=True, timeout=150):
        """Sends a diagnotistic message and returns the response"""
        msg = self.search_for(respID, respData, inDatabase=inDatabase)
        if msg:
            self.send_message(sendID, sendData, inDatabase=inDatabase)
            return self._block_unless_found(msg.txId, timeout)
        return False

    def start_logging(self, path):
        """Logs CAN traffic to a file"""
        if not self.initialized:
            logging.error('Initialization required to begin logging!')
            return False
        if not self.receiving:
            self.receiving = True
            self.stopRxThread = Event()
            msgEvent = CreateEvent(None, 0, 0, None)
            msgPointer = pointer(c_int(msgEvent.handle))
            self.status = setNotification(self.portHandle, msgPointer, 1)
            self._printStatus('Set Notification')
            self.rxthread = receiveThread(self.stopRxThread, self.portHandle,
                                          msgEvent)
            path = self.rxthread.logTo(path)
            self.rxthread.start()
        else:
            path = self.rxthread.logTo(path)
        return path

    def stop_logging(self):
        """Stops CAN logging"""
        if not self.receiving:
            logging.error('Not currently logging!')
            return False

        self.rxthread.stopLogging()

        if not self.rxthread.busy():
            self.stopRxThread.set()
            self.receiving = False

        return True

    def print_periodics(self, info=False, searchFor=''):# pylint: disable=R0912
        """Prints all periodic messages currently being sent"""
        if not self.sendingPeriodics:
            logging.info('No periodics currently being sent')
        if searchFor:
            # pylint: disable=W0612
            (status, msgID) = self._checkMsgID(searchFor)
            if not status:
                return False
            elif status == 1:  # searching periodics by id
                for periodic in self.currentPeriodics:
                    if periodic.txId == msgID:
                        self.lastFoundMessage = periodic
                        self._printMessage(periodic)
                        for sig in periodic.signals:
                            self.lastFoundSignal = sig
                            self._printSignal(sig, value=True)
            else:  # searching by string or printing all
                found = False
                for msg in self.currentPeriodics:
                    if searchFor.lower() in msg.name.lower():
                        found = True
                        self.lastFoundMessage = msg
                        self._printMessage(msg)
                        for sig in msg.signals:
                            self.lastFoundSignal = sig
                            self._printSignal(sig, value=True)
                    else:
                        msgPrinted = False
                        for sig in msg.signals:
                            #pylint: disable=E1103
                            shortName = (msgID.lower() in sig.name.lower())
                            fullName = (msgID.lower() in sig.fullName.lower())
                            #pylint: enable=E1103
                            if fullName or shortName:
                                found = True
                                if not msgPrinted:
                                    self.lastFoundMessage = msg
                                    self._printMessage(msg)
                                    msgPrinted = True
                                self.lastFoundSignal = sig
                                self._printSignal(sig, value=True)
                if not found:
                    logging.error(
                        'Unable to find a periodic message with that string!')
        else:
            for msg in self.currentPeriodics:
                self.lastFoundMessage = msg
                self._printMessage(msg)
                if info:
                    for sig in msg.signals:
                        self.lastFoundSignal = sig
                        self._printSignal(sig, value=True)
            if self.sendingPeriodics:
                print 'Currently sending: '+str(len(self.currentPeriodics))

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
                dlc = len(data)/2
                sender = ''
                for node in self.parser.dbc.nodes.values():
                    if node.sourceID == msgID&0xFFF:
                        sender = node.name
                msg = pydbc.DBCMessage(msgID, 'Unknown', dlc, sender, [], None,
                                       None, None)
                msg.txId = msgID
                msg.cycleTime = 0
        else: # string
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

    def _updateSignals(self, msg): # pylint: disable=R0201
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
        elif (type(msgID) == IntType) or (type(msgID) == LongType):
            caseNum = 1
        else:
            caseNum = 0
            logging.error('Invalid message id - non-string and non-numeric!')
        if caseNum == 1:
            if (msgID > 0xFFFFFFFF) or (msgID < 0):
                caseNum = 0
                logging.error('Invalid message id - negative or too large!')
        return (caseNum, msgID)

    def _checkMsgData(self, msg, data): # pylint: disable=R0201
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

    def _reverse(self, num, dlc): # pylint: disable=R0201
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
    #pylint:disable=R0912
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
        if not self.parser.dbc.messages.has_key(sig.msgID):
            logging.error('Message not found!')
            return False
        msg = self.parser.dbc.messages[sig.msgID]
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
                        logging.error('Value \'%s\' not found for signal \'%s\'!', value, sig.fullName)
                        return False
                else:
                    try:
                        float(value)
                        if value not in sig.values.values():
                            logging.error('Value \'%s\' not found for signal \'%s\'!', value, sig.fullName)
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
            if not sig.setVal(value, force=force):
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
    #pylint:enable=R0912
    def _printMessage(self, msg):
        """Prints a colored CAN message"""
        print ''
        msgid = hex(msg.txId)
        data = hex(msg.data)[2:]
        if msgid[-1] == 'L':
            msgid = msgid[:-1]
        if data[-1] == 'L':
            data = data[:-1]
        while len(data) < (msg.dlc*2):
            data = '0'+data
        if msg.endianness != 0:
            data = self._reverse(data, msg.dlc)
        txt = Style.BRIGHT+Fore.GREEN+'Message: '+msg.name+' - ID: '+msgid
        print txt+' - Data: 0x'+data
        if msg.cycleTime != 0:
            sending = 'Not Sending'
            color = Fore.WHITE+Back.RED
            if msg.sending:
                sending = 'Sending'
                color = Fore.WHITE+Back.GREEN
            txt = ' - Cycle time(ms): '+str(msg.cycleTime)+' - Status: '
            txt2 = color+sending+Back.RESET+Fore.MAGENTA+' - TX Node: '
            print txt+txt2+msg.sender+Fore.RESET+Style.RESET_ALL
        else:
            txt = ' - Non-periodic'+Fore.MAGENTA+' - TX Node: '
            print txt+msg.sender+Fore.RESET+Style.RESET_ALL
    # pylint: disable=R0912,R0201
    def _printSignal(self, sig, shortName=False, value=False):
        """Prints a colored CAN signal"""
        color = Fore.CYAN+Style.BRIGHT
        rst = Fore.RESET+Style.RESET_ALL
        if not shortName and not sig.fullName:
            shortName = True
        if shortName:
            name = sig.name
        else:
            name = sig.fullName
        if sig.values.keys():
            if value:
                print color+' - Signal: '+name
                print '            ^- '+str(sig.getVal())+rst
            else:
                print color+' - Signal: '+name
                sys.stdout.write('            ^- [')
                multiple = False
                for key, val in sig.values.items():
                    if multiple:
                        sys.stdout.write(', ')
                    sys.stdout.write(key+'('+hex(val)+')')
                    multiple = True
                sys.stdout.write(']'+rst+'\n')
        else:
            if value:
                print color+' - Signal: '+name
                print '            ^- '+str(sig.getVal())+sig.units+rst
            else:
                print color+' - Signal: '+name
                txt = '            ^- ['+str(sig.min_val)+' : '
                print txt+str(sig.max_val)+']'+rst
    # pylint: enable=R0912,R0201
    def _printStatus(self, item):
        """Prints the status of a vxlapi function call"""
        logging.debug("{0}: {1}".format(item, str(getError(self.status))))


def _split_lines(line):
    # Chop the first line at 54 chars
    output = ''
    isparam = True if line.count('@') else False
    while (len(line)-line.count('\t')-line.count('\n')) > 54:
        nlindex = line[:54].rindex(' ')
        output += line[:nlindex]+'\n\t\t\t'
        if isparam:
            output += '  '
        line = line[nlindex+1:]
    output += line
    return output


def _print_help(methods):
    """prints help text similarly to argparse"""
    for name, doc in methods:
        if len(name) < 12:
            firsthalf = '    '+name+'\t\t'
        else:
            firsthalf = '    '+name+'\t'
        secondhalf = ' '.join([i.strip() for i in doc.splitlines()]).strip()
        if secondhalf.count('@'):
            secondhalf = '\n\t\t\t  @'.join(secondhalf.split('@'))
        tmp = ''
        lines = secondhalf.splitlines()
        editedlines = ''
        for line in lines:
            if line.count('@'):
                line = '\n'+line
            if (len(line)-line.count('\t')-line.count('\n')) > 54:
                editedlines += _split_lines(line)
            else:
                editedlines += line

        print firsthalf+editedlines
    print '    q | exit\t\tTo exit'


def main():
    """Run the command-line program for the current class"""
    logging.basicConfig(format=settings.DEFAULT_DEBUG_MESSAGE,
                        level=logging.INFO)

    parser = ArgumentParser(prog='can', description='A license free '+
                            'interface to the CAN bus', add_help=False)
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="enable verbose output")
    parser.add_argument('-c', '--channel', help='the CAN channel or port to'+
                        ' connect to')
    parser.add_argument('-nl', '--network-listen', action='store_true',
                        help='start the program in network mode. it will then '+
                        'begin listening for commands on a port related to the'+
                        ' can channel')
    parser.add_argument('-ns', '--network-send', metavar='cmd', type=str,
                        nargs='+', help='commands to send to a separate '+
                        'instance of the program running in network mode')

    methods = []
    classes = [CAN]
    for can_class in classes:
        # Collect the feature's helper methods
        #skips = [method[0] for method in
        #         inspect.getmembers(can_class.__bases__[0],
        #                            predicate=inspect.ismethod)]
        for name, method in inspect.getmembers(can_class,
                                               predicate=inspect.ismethod):
            if not name.startswith('_') and method.__doc__:
                methods.append((name, method.__doc__ + '\n\n'))
    if methods:
        methods.sort()

    args = parser.parse_args()

    if not args.channel:
        channel = config.get(config.PORT_CAN_ENV)
        if not channel:
            parser.error('please specify a CAN channel')
        else:
            channel = int(channel)
    else:
        try:
            channel = int(args.channel)
        except ValueError:
            parser.error('please specify a valid CAN channel')
    if args.network_send:
        messages = args.network_send
        HOST = 'localhost'
        PORT = 50000+(2*channel)
        sendSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sendSock.connect((HOST, PORT))
        except socket.error:
            logging.error('Unable to connect to can!\n\nCheck that a verion'+
                          ' is running in network mode and that the channel'+
                          ' specified\nis correct.')
            sys.exit(1)
        sendSock.sendall(' '.join(messages))
        print sendSock.recv(128)
        sendSock.close()
        sys.exit(0)
    if args.verbose:
        logging.basicConfig(format=settings.VERBOSE_DEBUG_MESSAGE,
                            level=logging.DEBUG)
    else:
        logging.basicConfig(format=settings.DEFAULT_DEBUG_MESSAGE,
                            level=logging.INFO)

    validCommands = [x[0] for x in methods]

    dbc_path = config.get(config.DBC_PATH_ENV)
    baudrate = config.get(config.CAN_BAUD_RATE_ENV)
    HOST = ''
    PORT = 50000+(2*channel)
    sock = None
    conn = None
    if args.network_listen:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((HOST, PORT))
        sock.listen(1)
    can = CAN(channel, dbc_path, baudrate)
    can.start()
    print 'Type an invalid command to see help'
    while 1:
        try:
            if not args.network_listen:
                o = raw_input('> ')
            else:
                waiting = True
                while waiting:
                    inputr, [], [] = select.select([sock], [], [], 3)
                    for s in inputr:
                        if s == sock:
                            waiting = False
                conn, addr = sock.accept() # pylint: disable=W0612
                o = conn.recv(128)
            if o:
                s = shlex.split(o)
                logging.debug(s)
                command = s[0]
                if command in validCommands:
                    try:
                        resp = getattr(can, command)(*s[1:])
                        if args.network_listen:
                            conn.sendall(str(resp))
                    except Exception:
                        raise
                elif command in ['exit', 'q']:
                    break
                elif command == 'alive':
                    if args.network_listen:
                        conn.sendall('yes')
                    else:
                        _print_help(methods)
                else:
                    if not args.network_listen:
                        _print_help(methods)
                    else:
                        conn.sendall('invalid command')
                if args.network_listen:
                    conn.close()
        except EOFError:
            pass
        except KeyboardInterrupt:
            if args.network_listen and conn:
                conn.close()
            break
        except Exception:
            if args.network_listen and conn:
                conn.close()
            print '-' * 60
            traceback.print_exc(file=sys.stdout)
            print '-' * 60
            break
    sys.stdout.flush()

if __name__ == "__main__":
    main()
