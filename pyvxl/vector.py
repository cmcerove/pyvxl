#!/usr/bin/env python

"""Contains the CAN class for interacting with vector hardware."""

import traceback
import time
import logging
import os
import sys
import inspect
import socket
import select
import shlex
from copy import deepcopy
from argparse import ArgumentParser
from pyvxl import pydbc, settings, config
from pyvxl.transmit import Transmit
from pyvxl.receive import Receive
from colorama import init, Fore, Back, Style

__program__ = 'can'


class CAN(object):
    """Simulate CAN traffic."""

    def __init__(self, channel, dbc_path, baudrate):
        """."""
        self.dbc_path = dbc_path
        self.tx_proc = Transmit(int(channel), baudrate)
        self.rx_proc = Receive(int(channel), baudrate)
        self.baudrate = baudrate
        self.imported = False
        self.last_found_msg = None
        self.last_found_sig = None
        self.last_found_node = None
        self.init_channel = 0
        self.channel = 0
        self.txthread = None
        self.parser = None
        self.validMsg = (None, None)
        init()
        self.import_dbc()

    def __del__(self):
        """."""
        self.tx_proc.__del__()
        self.rx_proc.__del__()

    def import_dbc(self):
        """Import the selected dbc."""
        dbcname = self.dbc_path.split('\\')[-1]
        if not os.path.exists(self.dbc_path):
            raise AssertionError('Path: "{0}"'
                                 ' does not exist!'.format(self.dbc_path))
        try:
            self.parser = pydbc.importDBC(self.dbc_path)
            self.imported = True
            logging.info('Successfully imported: {}'.format(dbcname))
            return True
        except Exception:
            self.imported = False
            logging.error('Import failed!')
            logging.info('-' * 60)
            traceback.print_exc(file=sys.stdout)
            logging.info('-' * 60)
            raise

    def start_logging(self, path):
        """Start logging."""
        return self.rx_proc.start_logging(path)

    def stop_logging(self):
        """Stop logging."""
        return self.rx_proc.stop_logging()

    def start_node(self, node):
        """Send all periodic messages for node."""
        raise NotImplementedError

    def start_nodes_except(self, node):
        """Send all periodic messages except those transmitted by node."""
        if not self.imported:
            self.import_dbc()
        if not isinstance(node, str):
            raise ValueError('Expected {} but got {}'.format(str, type(node)))
        if node.lower() not in self.parser.dbc.nodes:
            # Prevent simulating traffic from all nodes since this has no
            # testing value and would most likely be done in error.
            raise ValueError('Node {} not found in the dbc'.format(node))
        for curr_node in self.parser.dbc.nodes:
            if curr_node != node:
                self.start_node(curr_node)

    def stop_node(self, node):
        """Stop all periodic messages from node."""
        removed = False
        if not self.tx_proc.is_transmitting():
            logging.error('No periodics to stop!')
        try:
            if isinstance(node, str):
                try:
                    # test for decimal string
                    node = int(node)
                except ValueError:
                    node = int(node, 16)
        except ValueError:
            pass
        if isinstance(node, int) or isinstance(node, long):
            if node > 0xFFF:
                logging.error('Node value is too large!')
                return False
            self.find_node(node)
            if self.last_found_node:
                node = self.last_found_node.name
            else:
                logging.error('Invalid node number!')
                return False
        elif not isinstance(node, str):
            logging.error('Invalid node type!')
            return False
        for msg in self.tx_proc.messages:
            if msg.sender.lower() == node.lower():
                removed = True
                self.stop_message(msg.id)
        if not removed:
            logging.error('No periodics currently being sent by that node!')
        return removed

    def send_signal(self, signal, value, send_once=False, force=False):
        """Send the message containing signal."""
        msg = self._check_signal(signal, value, force)
        logging.debug('send_signal - msg 0x{:X} - data {}'
                      ''.format(msg.id, msg.get_data()))
        if msg.period == 0 or send_once:
            self.tx_proc.transmit_once(msg)
        else:
            self.tx_proc.add(msg)

    def stop_signal(self, sig_name):
        """Stop a periodic message based on the signal name."""
        msg = self._check_signal(sig_name)
        self.tx_proc.remove(msg.id)
        logging.info('Stopped message ID: 0x{:X}'.format(msg.id))

    def send_message(self, msg_id, data='', period=0, send_once=False,
                     in_database=True):
        """Send a spontaneous or periodic message."""
        msg = self._get_message_obj(msg_id, data, period, in_database)
        if data:
            msg.set_data(data)

        logging.debug('Msg ID {:X} Data {} Period {}ms'
                      ''.format(msg.id, msg.get_data(), msg.period))
        if msg.period == 0 or send_once:
            self.tx_proc.transmit_once(msg)
        else:
            self.tx_proc.add(msg)

    def stop_message(self, msg_id):
        """Stop a periodic message based on the message name or id."""
        if self.tx_proc.is_transmitting():
            msg = self._get_message_obj(msg_id)
            if self.tx_proc.is_transmitting(msg.id):
                self.tx_proc.remove(msg.id)
                logging.info('Stopped message ID: 0x{:X}'.format(msg.id))
            else:
                logging.warning('Message ID: 0x{:X} is already stopped!'
                                ''.format(msg.id))
        else:
            logging.warning('Periodics already stopped!')

    def stop_all_messages(self):
        """Stop all periodic messages."""
        if self.tx_proc.is_transmitting():
            self.tx_proc.remove_all()
        else:
            logging.warning('Periodics already stopped!')

    def stop_periodic(self, name):
        """(DEPRECATED) Stop a periodic message.

        @param name: signal name or message name or message id
        """
        logging.warning('stop_periodic is deprecated; please use stop_signal'
                        ' or stop_message instead.')
        if self.tx_proc.is_transmitting():
            name = self._check_type(name)
            if isinstance(name, int) or isinstance(name, long):
                # Signals can't be numbers, so try and stop this message
                self.stop_message(name)
            else:
                # value is a string
                # Could be a message name or signal name
                try:
                    msg = self._get_message_obj(name)
                except ValueError:
                    # Couldn't find a matching message, maybe it's a signal
                    try:
                        msg = self._check_signal(name)
                    except ValueError:
                        raise ValueError('No messages or signals named {}!'.format(name))
                self.tx_proc.remove(msg.id)
                logging.info('Stopped message ID: 0x{:X}'.format(msg.id))
        else:
            logging.error('No periodic with that value to stop!')

    def stop_periodics(self):
        """(DEPRECATED) Stop all periodic messages."""
        logging.warning('stop_periodics is deprecated;'
                        ' please use stop_all_messages instead')
        self.stop_all_messages()

    def find_node(self, node):
        """Search the dbc for node."""
        if not self.imported:
            self.import_dbc()
        node = self._check_type(node)
        numFound = 0
        for anode in self.parser.dbc.nodes.values():
            if isinstance(node, int) or isinstance(node, long):
                if node == anode.sourceID:
                    numFound += 1
                    self.last_found_node = anode
            else:
                if node.lower() in anode.name.lower():
                    numFound += 1
                    self.last_found_node = anode
                    if display:
                        txt = Fore.MAGENTA+Style.DIM+'Node: '+anode.name
                        txt2 = ' - ID: '+hex(anode.sourceID)
                        logging.info(txt+txt2+Fore.RESET+Style.RESET_ALL)
        if numFound == 0:
            self.last_found_node = None
            logging.info('No nodes found for that input')
        elif numFound > 1:
            self.last_found_node = None

    def find_message(self, msg, display=False, exact=True):
        """Search the dbc for message names containing msg."""
        self.last_found_msg = None
        if not self.imported:
            self.import_dbc()
        numFound = 0
        msg_id = self._check_type(msg)
        if isinstance(msg_id, int) or isinstance(msg_id, long):
            try:
                if msg_id > 0x8000:
                    #msg_id = (msg_id&~0xF0000FFF)|0x80000000
                    msg_id |= 0x80000000
                    msg = self.parser.dbc.messages[msg_id]
                else:
                    msg = self.parser.dbc.messages[msg_id]
                numFound += 1
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
            for msg in self.parser.dbc.messages.values():
                if not exact:
                    if msg_id.lower() in msg.name.lower():
                        numFound += 1
                        self.last_found_msg = msg
                        if display:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
                else:
                    if msg_id.lower() == msg.name.lower():
                        numFound += 1
                        self.last_found_msg = msg
                        if display:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
        if numFound == 0:
            self.last_found_msg = None
            if display:
                logging.info('No messages found for that input')
        elif numFound > 1:
            self.last_found_msg = None
        return True

    def find_signal(self, signal, display=False):
        """Search the dbc for signal names containing sig."""
        if not signal or not isinstance(signal, str):
            raise TypeError('Expected str, but got {}'.format(type(signal)))
        if not self.imported:
            self.import_dbc()
        numFound = 0
        for msg in self.parser.dbc.messages.values():
            msgPrinted = False
            for sig in msg.signals:
                shortName = (signal.lower() in sig.name.lower())
                fullName = (signal.lower() in sig.fullName.lower())
                if fullName or shortName:
                    logging.debug('Found signal {} ({})'.format(sig.fullName,
                                                                sig.name))
                    numFound += 1
                    self.last_found_sig = sig
                    self.last_found_msg = msg
                    if display:
                        if not msgPrinted:
                            self._print_msg(msg)
                            msgPrinted = True
                        self._print_sig(sig)
        if numFound == 0:
            self.last_found_sig = None
            logging.info('No signals found for that input')
        elif numFound > 1:
            self.last_found_sig = None
        return True

    def get_message(self, msg):
        """Return the message object associated with msg."""
        ret = None
        if self.find_message(msg) and self.last_found_msg:
            ret = self.last_found_msg
        return ret

    def get_signals(self, msg):
        """Return the list of signals in msg."""
        ret = None
        if self.find_message(msg) and self.last_found_msg:
            ret = self.last_found_msg.signals
        return ret

    def get_signal_values(self, sig):
        """Return a dictionary of valid signal values for sig."""
        ret = None
        if self.find_signal(sig) and self.last_found_sig:
            ret = self.last_found_sig.values
        return ret

    def wait_for_error(self):
        """Block until the CAN bus goes into an error state."""
        while not self.rx_proc.errors_found():
            time.sleep(0.001)

        self.stop_periodics()
        self.tx_proc.vxl.reconnect()
        return

    def _block_unless_found(self, msg_id, timeout):
        foundData = ''
        startTime = time.clock()
        timeout = float(timeout) / 1000.0

        while (time.clock() - startTime) < timeout:
            time.sleep(0.01)
            foundData = self.rx_proc.getFirstRxMessage(msg_id)
            if foundData:
                break

        if foundData:
            return foundData
        else:
            return False

    def wait_for(self, msg_id, data='', timeout=1000, in_database=True):
        """Wait for a specific message or timeout is reached."""
        resp = False
        msg = self.search_for(msg_id, data, in_database=in_database)
        if msg:
            resp = self._block_unless_found(msg.id, timeout)

        return resp

    def search_for(self, msg_id, data='', in_database=True):
        """Add a message to the search queue."""
        # a mask of don't care data
        dc_mask = ''
        if isinstance(data, str) and '*' in data:
            # Found wildcards, populate the dc_mask
            tmpData = []
            mask = []
            for x in range(len(data)):
                if data[x] == '*':
                    tmpData.append('0')
                    mask.append('0000')
                else:
                    tmpData.append(data[x])
                    mask.append('1111')
            dc_mask = int(''.join(mask), 2)
            data = int(''.join(tmpData), 16)
        msg = self._get_search_message(msg_id, data, in_database)
        self.rx_proc.search_for(msg, dc_mask)

        return msg

    def clear_search_queue(self):
        """Clear the received message queue."""
        return self.rx_proc.clearSearchQueue()

    def stop_searching_for(self, msg_id, in_database=True):
        """Remove a message from the search queue."""
        resp = False
        msg, data = self._get_search_message(msg_id, '', in_database)
        if msg:
            resp = self.rx_proc.stop_searching_for(msg.id)
        return resp

    def get_first_rx_message(self, msg_id=False):
        """Return the first received message."""
        return self.rx_proc.get_first_rx_message(msg_id)

    def get_all_rx_messages(self, msg_id=False):
        """Return all received messages."""
        return self.rx_proc.get_all_rx_messages(msg_id)

    def print_periodics(self, info=False, search_for=''):
        """Print all periodic messages currently being sent."""
        raise NotImplementedError('This function needs some work')
        if not self.tx_proc.is_transmitting():
            logging.info('No periodics currently being sent')
        if search_for:
            msg_id = self._check_type(search_for)
            if isinstance(msg_id, int) or isinstance(msg_id, long):
                for periodic in self.tx_proc.messages:
                    if periodic.id == msg_id:
                        self.last_found_msg = periodic
                        self._print_msg(periodic)
                        for sig in periodic.signals:
                            self.last_found_sig = sig
                            self._print_sig(sig, value=True)
            else:  # searching by string or printing all
                found = False
                for msg in self.tx_proc.messages:
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
                            shortName = (msg_id.lower() in sig.name.lower())
                            fullName = (msg_id.lower() in sig.fullName.lower())
                            if fullName or shortName:
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
            for msg in self.tx_proc.messages:
                self.last_found_msg = msg
                self._print_msg(msg)
                if info:
                    for sig in msg.signals:
                        self.last_found_sig = sig
                        self._print_sig(sig, value=True)
            if self.tx_proc.messages:
                print('Currently sending: {}'.format(len(self.tx_proc.messages)))

    def _get_search_message(self, msg_id, data, in_database):
        """Return a message and data to be used for searching received messages."""
        # Create a copy of the database message object
        search_msg = deepcopy(self._get_message_obj(msg_id, data, in_database=in_database))
        if data:
            search_msg.set_data(data)
        return search_msg

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
                else:
                    raise ValueError('Message ID: 0x{:X} not found in the'
                                     ' database!'.format(msg_id))
            else:
                data = data.replace(' ', '')
                dlc = (len(data) / 2) + (len(data) % 2)
                msg = pydbc.DBCMessage(msg_id, 'Unknown', dlc, '', [], None,
                                       None, None)
                msg.period = period
        else:
            # string
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

    def _print_msg(self, msg):
        """Print a colored CAN message."""
        print('')
        msg_id = hex(msg.id)
        data = hex(msg.data)[2:]
        if msg_id[-1] == 'L':
            msg_id = msg_id[:-1]
        if data[-1] == 'L':
            data = data[:-1]
        data = data.zfill(msg.dlc * 2)
        if msg.endianness != 0:
            data = self._reverse(data, msg.dlc)
        txt = Style.BRIGHT+Fore.GREEN+'Message: '+msg.name+' - ID: '+msg_id
        print(txt+' - Data: 0x'+data)
        if msg.period != 0:
            sending = 'Not Sending'
            color = Fore.WHITE+Back.RED
            if msg.sending:
                sending = 'Sending'
                color = Fore.WHITE+Back.GREEN
            txt = ' - Cycle time(ms): '+str(msg.period)+' - Status: '
            txt2 = color+sending+Back.RESET+Fore.MAGENTA+' - TX Node: '
            print(txt+txt2+msg.sender+Fore.RESET+Style.RESET_ALL)
        else:
            txt = ' - Non-periodic'+Fore.MAGENTA+' - TX Node: '
            print(txt+msg.sender+Fore.RESET+Style.RESET_ALL)

    def _print_sig(self, sig, shortName=False, value=False):
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
                print(color+' - Signal: '+name)
                print('            ^- '+str(sig.get_val())+rst)
            else:
                print(color+' - Signal: '+name)
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
                print(color+' - Signal: '+name)
                print('            ^- '+str(sig.get_val())+sig.units+rst)
            else:
                print(color+' - Signal: '+name)
                txt = '            ^- ['+str(sig.min_val)+' : '
                print(txt+str(sig.max_val)+']'+rst)


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

        print(firsthalf+editedlines)
    print('    q | exit\t\tTo exit')


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
        print(sendSock.recv(128))
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
    print('Type an invalid command to see help')
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
                conn, addr = sock.accept()
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
            print('-' * 60)
            traceback.print_exc(file=sys.stdout)
            print('-' * 60)
            break
    sys.stdout.flush()

if __name__ == "__main__":
    main()
