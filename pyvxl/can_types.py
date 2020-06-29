#!/usr/bin/env python3

"""CAN types used by pyvxl.CAN."""

import logging
from os import path
from sys import exit, argv
from pyvxl.pydbc import DBCParser
from colorama import Fore, Back, Style
from colorama import init as colorama_init
from colorama import deinit as colorama_deinit


class Database:
    """A CAN database."""

    def __init__(self, db_path): # noqa
        self.__nodes = {}
        self.__messages = {}
        self.__signals = {}
        self.last_found_node = None
        self.last_found_msg = None
        self.last_found_sig = None
        self.path = db_path

    def __str__(self):
        """Return a string representation of this database."""
        return (f'Database({path.basename(self.path)})')

    @property
    def path(self):
        """The path to the database."""
        return self.__path

    @path.setter
    def path(self, db_path):
        """Set the database path and import it."""
        if not isinstance(db_path, str):
            raise TypeError(f'Expected str but got {type(db_path)}')
        if not path.isfile(db_path):
            raise ValueError(f'Database {db_path} does not exist')
        _, ext = path.splitext(db_path)
        # TODO: Implement .arxml import
        supported = ['.dbc']
        if ext not in supported:
            raise TypeError(f'{db_path} is not supported. Supported file '
                            f'types: {supported}')
        if ext == '.dbc':
            self.__import_dbc(db_path)

    def __import_dbc(self, db):
        """Import a dbc."""
        self.__path = db
        p = DBCParser(db, Node, Message, Signal, write_tables=0, debug=False)
        if not p.messages:
            raise ValueError('{} contains no messages or is not a valid dbc.'
                             ''.format(db))

        self.__nodes = p.nodes
        self.__messages = p.messages
        self.__signals = p.signals

        msb_map = {}
        for x in range(1, 9):
            little_endian = 0
            big_endian = (x - 1) * 8
            ret = {}
            for i in range(int(x / 2) * 8):
                ret[big_endian] = little_endian
                ret[little_endian] = big_endian
                little_endian += 1
                big_endian += 1
                if big_endian % 8 == 0:
                    big_endian -= 16
            msb_map[x] = ret

        for msg in p.messages.values():
            if msg.send_type_num is not None and\
               msg.send_type_num < len(p.send_types):
                msg.send_type = p.send_types[msg.send_type_num]

            setendianness = False
            for sig in msg.signals:
                if not setendianness:
                    if msg.id > 0xFFFF:
                        if msg.sender.lower() in p.nodes:
                            sender = p.nodes[msg.sender.lower()].source_id
                            if (sender & 0xF00) > 0:
                                print(msg.name)
                            msg.id = (msg.id & 0xFFFF000) | 0x10000000 | sender
                        else:
                            print(msg.sender, msg.name)
                    msg.endianness = sig.endianness
                    setendianness = True
                if msg.dlc > 0:
                    if sig.bit_msb in msb_map[msg.dlc]:
                        sig.bit_start = msb_map[msg.dlc][sig.bit_msb] - (sig.bit_len-1)
                    else:
                        sig.bit_start = sig.bit_msb - (sig.bit_len - 1)
                    sig.set_mask()
                    if sig.init_val is not None:
                        sig.set_val(sig.init_val * sig.scale + sig.offset)

    @property
    def nodes(self):
        """A dictionary of imported nodes."""
        return self.__nodes

    def get_node(self, name):
        """Get a node by name."""
        pass

    def find_node(self, name):
        """Find nodes by name."""

    @property
    def messages(self):
        """A dictionary of imported messages stored by message name."""
        return self.__messages

    def get_message(self, name_or_id):
        """Get a message by name or id."""
        ret = None
        if self.find_message(name_or_id, exact=True) and self.last_found_msg:
            ret = self.last_found_msg
        return ret

    def find_message(self, name_or_id, exact=False, print_result=False):
        """Find messages by name or id.

        Returns a list of message objects.
        """
        num_found = 0
        msg_id = self._check_message(name_or_id)
        if isinstance(msg_id, int):
            try:
                if msg_id > 0x8000:
                    # msg_id = (msg_id&~0xF0000FFF)|0x80000000
                    msg_id |= 0x80000000
                    msg = self.imported.messages[msg_id]
                else:
                    msg = self.imported.messages[msg_id]
                num_found += 1
                self.last_found_msg = msg
                if print_result:
                    self._print_msg(msg)
                    for sig in msg.signals:
                        self._print_sig(sig)
            except KeyError:
                logging.error('Message ID 0x{:X} not found!'.format(msg_id))
                self.last_found_msg = None
                return False
        else:
            for msg in self.messages.values():
                if not exact:
                    if msg_id.lower() in msg.name.lower():
                        num_found += 1
                        self.last_found_msg = msg
                        if print_result:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
                else:
                    if msg_id.lower() == msg.name.lower():
                        num_found += 1
                        self.last_found_msg = msg
                        if print_result:
                            self._print_msg(msg)
                            for sig in msg.signals:
                                self._print_sig(sig)
        if num_found == 0:
            self.last_found_msg = None
            if print_result:
                logging.info('No messages found for that input')
        elif num_found > 1:
            self.last_found_msg = None
        return True

    def _check_message(self, msg_id):
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
        msg_id = self._check_message(msg_id)
        # Find the message id based on the input type
        if isinstance(msg_id, int):
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
                msg = Message(msg_id, 'Unknown', dlc)
                msg.period = period
        elif isinstance(msg_id, str):
            for message in self.messages.values():
                if msg_id.lower() == message.name.lower():
                    msg = message
                    break
            else:
                raise ValueError('Message Name: {} not found in the'
                                 ' database!'.format(msg_id))
        return msg

    @property
    def signals(self):
        """A dictionary of imported signals."""
        return self.__signals

    @signals.setter
    def signals(self, sig):
        """Add a signal to the dictionary."""
        if not isinstance(sig, Signal):
            raise TypeError(f'Expected {Signal} but got {type(sig)}')
        self.__signals[sig.name] = sig

    def get_signal(self, name):
        """Get a signal by name."""
        return self.find_signal(name, exact=True)

    def find_signal(self, name, exact=False):
        """Find signals by name."""
        if not isinstance(name, str):
            raise TypeError(f'Expected str, but got {type(name)}')
        num_found = 0
        for msg in self.messages.values():
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

    def _check_signal(self, signal, value=None, force=False):
        """Check the validity of a signal and optionally it's value.

        Returns the message object containing the updated signal on success.
        """
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


class Node:
    """A CAN node."""

    def __init__(self, name):  # noqa
        self.name = name
        self.source_id = 0
        self.tx_messages = []

    @property
    def name(self):
        """The name of the node."""
        return self.__name

    @name.setter
    def name(self, name):
        """Set the name of the node."""
        if isinstance(name, str):
            self.__name = name
        else:
            raise TypeError(f'Expected str but got {type(name)}')


class Message:
    """A CAN message."""

    def __init__(self, msgid, name, length, sender=None, signals=[]):  # noqa
        self.id = int(msgid)
        self.name = name
        self.dlc = length
        self.sender = sender
        self.signals = signals
        for signal in signals:
            signal.add_msg_ref(self)
        self.__data = 0
        self.endianness = 0
        self.period = 0
        self.delay = None
        self.send_type_num = None
        self.send_type = None
        self.repetitions = None
        self.sending = False
        self.update_func = None

        # TODO: Populate this on import
        self.transmitters = None

    @property
    def name(self):
        """The name of the message."""
        return self.__name

    @name.setter
    def name(self, name):
        """Set the name of the message."""
        if isinstance(name, str):
            self.__name = name
        else:
            raise TypeError(f'Expected str but got {type(name)}')

    # if msg.send_type_num is not None and\
    #    msg.send_type_num < len(p.send_types):
    #     msg.send_type = p.send_types[msg.send_type_num]
    # pass

    @property
    def data(self):
        """A 64 bit int of all message data."""
        data = 0
        for sig in self.signals:
            # Clear the signal value in data
            data &= ~sig.mask
            # Set the value
            data |= sig.val
        return data

    def get_data(self):
        """Get the current message data based on each signal value.

        Returns a the current message data as a hexadecimal string
        padded with zeros to the message length.
        """
        return f'{self.data:0{self.dlc*2}X}'

    def set_data(self, data):
        """Update signal values based on data.

        Accepts a hexadecimal string or an integer.
        """
        if data:
            if isinstance(data, str):
                data = data.replace(' ', '')
                try:
                    data = int(data, 16)
                except ValueError:
                    raise ValueError('Cannot set data to non-hexadecimal'
                                     f' string {data}!')
            if isinstance(data, int):
                # Check for invalid length
                if len('{:X}'.format(data)) > (self.dlc * 2):
                    raise ValueError(f'{data:X} is longer than message length '
                                     f'of {self.dlc} bytes')
            else:
                raise TypeError(f'Expected an int or str but got {type(data)}')
                # Handling for messages without signals
            for sig in self.signals:
                sig.val = data & sig.mask
        else:
            logging.error('set_data called with no data!')

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
        colorama_init()
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
        colorama_deinit()


class Signal:
    """A CAN signal."""

    def __init__(self, name, mux, bit_msb, bit_len, endianness, signedness,
                 scale, offset, min_val, max_val, units, receivers):  # noqa
        """."""
        self.name = name
        self.mux = mux  # not implemented
        self.bit_msb = bit_msb
        self.bit_len = bit_len
        self.endianness = endianness
        self.signedness = signedness  # not implemented
        self.scale = scale
        self.offset = offset
        self.min_val = min_val
        self.max_val = max_val
        self.units = units
        self.receivers = receivers  # not implemented
        self.full_name = ''
        self.values = {}
        self.msg_id = 0
        self.val = 0
        self.init_val = None
        self.send_on_init = 0
        self.mask = 0
        self.bit_start = 0
        self.msg = None

    def __str__(self):
        """Return a string representation of this database."""
        return f'Signal({self.name})'

    @property
    def name(self):
        """The name of the signal."""
        return self.__name

    @name.setter
    def name(self, name):
        """Set the name of the signal."""
        if isinstance(name, str):
            self.__name = name
        else:
            raise TypeError(f'Expected str but got {type(name)}')

    def add_msg_ref(self, msg):
        """Add a reference to message this signal is included in."""
        self.msg = msg

    def set_val(self, value, force=False):
        """Set the signal's value based on the offset and scale."""
        negative = False

        # self.values will only be set if the signal has a discrete set of
        # values, otherwise the signal will be defined with min_val and max_val
        if self.values and not force:
            if isinstance(value, str):
                if value.lower() in self.values:
                    num = self.values[value]
                else:
                    raise ValueError('{} is invalid for {}; valid values = {}'
                                     ''.format(value, self.name, self.values))
            else:
                try:
                    num = float(value)
                    if value not in self.values.values():
                        raise ValueError('{} is invalid for {}; valid values ='
                                         ' {}'.format(value, self.name,
                                                      self.values))
                except ValueError:
                    raise ValueError('{} is invalid for {}; valid values = {}'
                                     ''.format(value, self.name, self.values))
        elif force:
            try:
                num = float(value)
            except ValueError:
                logging.error('Unable to force a non numerical value!')
        elif (float(value) < self.min_val) or (float(value) > self.max_val):
            raise ValueError('Value {} out of range! Valid range is {} to {}'
                             ' for signal {}.'.format(float(value),
                                                      self.min_val,
                                                      self.max_val,
                                                      self.name))
        else:
            num = value

        # Convert the number based on it's location
        num = int((float(num) - float(self.offset)) / float(self.scale))

        if num < 0:
            num = abs(num)
            negative = True

        size = len('{:b}'.format(num))
        if not force:
            if size > self.bit_len:
                raise ValueError('Unable to set {} to  {}; value too large!'
                                 ''.format(self.name, num))
                return False
        else:
            logging.warning('Ignoring dbc specs for this signal value')

        if negative:
            num = self._twos_complement(num)

        self.val = num << self.bit_start
        return True

    def get_val(self, raw=False):
        """Get the signal's value.

        Args:
            raw: If True, always returns the numeric value of the signal.
        """
        tmp = self.val >> self.bit_start
        curr_val = (tmp * self.scale + self.offset)
        # Check if curr_val should be negative
        if curr_val > 0 and self.min_val < 0:
            bval = '{:b}'.format(int(curr_val))
            if bval[0] == '1' and len(bval) == self.bit_len:
                curr_val = float(-self._twos_complement(int(curr_val)))

        if self.values:
            if not raw:
                for key, val in self.values.items():
                    if val == curr_val:
                        curr_val = key
            else:
                curr_val = int(curr_val)
        return curr_val

    def _twos_complement(self, num):
        """Return the twos complement value of a number."""
        tmp = '{:b}'.format(num)
        tmp = tmp.replace('0', '2')
        tmp = tmp.replace('1', '0')
        tmp = tmp.replace('2', '1')

        while len(tmp) < self.bit_len:
            tmp = '1' + tmp
        return int(tmp, 2) + 1

    def set_mask(self):
        """Set the signal's mask based on bit_start and bit_len."""
        if self.bit_start < 0:
            raise ValueError(f'{self}.bit_start is negative!')
        try:
            self.mask = 2 ** self.bit_len - 1 << self.bit_start
        except ValueError:
            print(self.bit_len, self.bit_start)

    def _check_signal(self, signal, value=None, force=False):
        """Check the validity of a signal and optionally it's value.

        Returns the message object containing the updated signal on success.
        """
        # TODO: delete after Database._check_signal is working
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

    def _print_sig(self, sig, short_name=False, value=False):
        """Print a colored CAN signal."""
        colorama_init()
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
        colorama_deinit()


import_str = '''
----------------------------------------------------
Import Statistics
----------------------------------------------------
Nodes: {}
Messages: {}
Signals: {}
----------------------------------------------------
'''


def main():  # noqa
    if len(argv) != 2:
        print(__doc__)
        exit(1)

    # Construct parser and parse file
    db = Database(argv[1])

    print(import_str.format(len(db.nodes), len(db.messages), len(db.signals)))

    if len(db.nodes) > 0:
        # The key for nodes is the node name in lowercase.
        _, node = db.nodes.popitem()
        print(f'N - {node.name}')
    if len(db.messages) > 0:
        # The key for messages is the message ID.
        _, message = db.messages.popitem()
        print(f'   M - {message.name}')
    if len(db.signals) > 0:
        # The key for signals is the signal name in lowercase.
        _, signal = db.signals.popitem()
        print(f'      S - {signal.name}')


if __name__ == '__main__':
    main()
