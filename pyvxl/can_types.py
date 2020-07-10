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
        self.path = db_path

    def __str__(self):
        """Return a string representation of this database."""
        string = 'Database(None)'
        if self.path is not None:
            string = f'Database({path.basename(self.path)})'
        return string

    @property
    def path(self):
        """The path to the database."""
        return self.__path

    @path.setter
    def path(self, db_path):
        """Set the database path and import it."""
        if db_path is not None:
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
        else:
            self.__path = None

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

        # TODO: move everything below into Node, Message and Signal classes
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
        """A dictionary of imported nodes stored by node name."""
        return self.__nodes

    def get_node(self, name):
        """Get a node by name."""
        if not isinstance(name, str):
            raise TypeError('Expected str but got {}'.format(type(name)))
        if name.lower() not in self.nodes:
            raise ValueError(f'Node {name} not found in database {self.path}')
        return self.__nodes[name.lower()]

    @property
    def messages(self):
        """A dictionary of imported messages stored by message id."""
        return self.__messages

    def add_message(self, msg_id, data, period, name):
        """Add a message to the database.

        Importing a database after adding messages will delete the added
        messages.
        """
        if msg_id in self.messages:
            raise ValueError(f'Message ID 0x{msg_id:X} is already in the '
                             'database')
        if not isinstance(data, str):
            raise TypeError(f'Expected str but got {type(data)}')
        data = data.replace(' ', '')
        dlc = sum(divmod(len(data), 2))
        msg = Message(msg_id, name, dlc)
        msg.period = period
        msg.data = data
        self.messages[msg.id] = msg
        return msg

    def get_message(self, name_or_id):
        """Get a message by name or id.

        Since messages are stored by message id, getting a message based on
        the message id is much faster than by name. Names also aren't required
        to be unique whereas message IDs are.
        """
        message = None
        if isinstance(name_or_id, str):
            for msg in self.messages.values():
                if name_or_id.lower() == msg.name.lower():
                    message = msg
                    break
            else:
                raise ValueError(f'{name_or_id} does not match a message name '
                                 f'or id in {self}')
        elif isinstance(name_or_id, int):
            # Strip the extended ID bit if it exists
            name_or_id &= 0x1fffffff
            if name_or_id not in self.messages:
                raise ValueError(f'{name_or_id} does not match a message name '
                                 f'or id in {self}')
            message = self.messages[name_or_id]
        else:
            raise TypeError(f'Expected str or int but got {type(name_or_id)}')
        return message

    def find_messages(self, name, print_result=False):
        """Find messages by name.

        Returns a list of message objects.
        """
        raise NotImplementedError
        messages = []
        num_found = 0
        msg_id = self._check_message(name_or_id)
        if isinstance(msg_id, int):
            name &= 0x1fffffff
            try:
                msg = self.imported.messages[msg_id]
                num_found += 1
                if print_result:
                    self._print_msg(msg)
                    for sig in msg.signals:
                        self._print_sig(sig)
            except KeyError:
                logging.error('Message ID 0x{:X} not found!'.format(msg_id))
                return False
        else:
            for msg in self.messages.values():
                if msg_id.lower() in msg.name.lower():
                    num_found += 1
                    if print_result:
                        self._print_msg(msg)
                        for sig in msg.signals:
                            self._print_sig(sig)
        if num_found == 0:
            if print_result:
                logging.info('No messages found for that input')
        elif num_found > 1:
            pass
        return True

    @property
    def signals(self):
        """A dictionary of imported signals stored by signal name."""
        return self.__signals

    def get_signal(self, name):
        """Get a signal by name."""
        signal = None
        if not isinstance(name, str):
            raise TypeError(f'Expected str but got {type(name)}')

        if name.lower() in self.signals:
            signal = self.signals[name]
        else:
            for sig in self.signals.values():
                if name.lower() == sig.long_name:
                    signal = sig
                    break
            else:
                raise ValueError(f'{name} does not match a short or long '
                                 f'signal name in {self}')

        return signal

    def find_signals(self, name, print_result=False):
        """Find signals by name.

        Returns a list of signals whose names contain the input name.
        """
        raise NotImplementedError
        signals = []
        if not isinstance(name, str):
            raise TypeError(f'Expected str, but got {type(name)}')
        num_found = 0
        for msg in self.messages.values():
            msgPrinted = False
            for sig in msg.signals:
                short_name = (search_str.lower() in sig.name.lower())
                full_name = (search_str.lower() in sig.long_name.lower())
                if full_name or short_name:
                    num_found += 1
                    if display:
                        if not msgPrinted:
                            self._print_msg(msg)
                            msgPrinted = True
                        self._print_sig(sig)
        if num_found == 0:
            logging.info('No signals found for that input')
        elif num_found > 1:
            pass
        return signals


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

    def __init__(self, msg_id, name, length, sender=None, signals=[]):  # noqa
        self.id = msg_id
        self.name = name
        self.dlc = length
        self.sender = sender
        self.signals = signals
        for signal in signals:
            signal.msg = self
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
        self.__init_completed = True

    @property
    def id(self):
        """The 11 or 29 bit ID for this message."""
        return self.__id

    @id.setter
    def id(self, msg_id):
        """Set the ID for this message."""
        msg_id = int(msg_id) & 0x1FFFFFFF
        if msg_id < 0:
            raise ValueError(f'msg_id {msg_id} must be positive!')
        try:
            _ = self.__id
        except AttributeError:
            self.__id = msg_id
        else:
            raise AssertionError('can\'t set attribute')

    @property
    def name(self):
        """The name of the message."""
        return self.__name

    @name.setter
    def name(self, name):
        """Set the name of the message."""
        if not isinstance(name, str):
            raise TypeError(f'Expected str but got {type(name)}')
        try:
            _ = self.__name
        except AttributeError:
            self.__name = name
        else:
            raise AssertionError('can\'t set attribute')

    @property
    def dlc(self):
        """The length of the message in bytes."""
        return self.__dlc

    @dlc.setter
    def dlc(self, dlc):
        """Set the length of the message in bytes."""
        if not isinstance(dlc, int):
            raise TypeError(f'Expected int but got {type(dlc)}')
        if dlc < 0 or dlc > 8:
            raise ValueError(f'{dlc} must be between 0 and 8')
        try:
            _ = self.__dlc
        except AttributeError:
            self.__dlc = dlc
            self.__max_val = int('FF' * dlc, 16)
        else:
            raise AssertionError('can\'t set attribute')

    @property
    def data(self):
        """An up to 64 bit int of all signal data."""
        data = 0
        if self.signals:
            for sig in self.signals:
                # Clear the signal value in data
                data &= ~sig.mask
                # Set the value
                data |= sig.raw_val
        else:
            data = self.__data
        return f'{data:0{self.dlc*2}X}'

    @data.setter
    def data(self, data):
        """Set the message data.

        Args:
            data: a hexadecimal string (spaces are ignored) or a int
        """
        if isinstance(data, str):
            data = data.replace(' ', '')
            try:
                data = int(data, 16)
            except ValueError:
                raise ValueError(f'{data} is not a hexadecimal string')
        elif not isinstance(data, int):
            raise TypeError(f'Expected a hex str or int but got {type(data)}')
        if data < 0 or data > self.__max_val:
            raise ValueError(f'{data:X} must be positive and less than the '
                             f'maximum value of {self.__max_val:X}!')
        if self.signals:
            for sig in self.signals:
                sig.value = data & sig.mask
        else:
            self.__data = data

    @property
    def period(self):
        """The transmit period of the message in milliseconds."""
        return self.__period

    @period.setter
    def period(self, period):
        """Set the transmit period for the message."""
        if not isinstance(period, int):
            raise TypeError(f'Expected int but got {type(period)}')
        self.__period = period

    def pprint(self):
        """Print colored info abnout the message to stdout."""
        colorama_init()
        print('')
        color = Style.BRIGHT + Fore.GREEN
        data = self.data
        if self.endianness != 0:
            data = bytes.fromhex(data)[::-1].hex()
        print(f'{color}Message: {self.name} - ID: 0x{self.id:X} - Data: '
              f'0x{data}')
        reset_color = Fore.RESET + Style.RESET_ALL
        node_color = Back.RESET + Fore.MAGENTA
        cycle_status = ' - Non-periodic'
        node = f'{node_color} - TX Node: {self.sender}{reset_color}'
        if self.period != 0:
            sending = 'Not Sending'
            send_color = Fore.WHITE + Back.RED
            if self.sending:
                sending = 'Sending'
                send_color = Fore.WHITE + Back.GREEN
            cycle_status = (f' - Cycle time(ms): {self.period}'
                            f' - Status: {send_color}{sending}')
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
        self.long_name = ''
        self.bit_start = 0
        self.values = {}
        self.value = 0
        self.init_val = None
        self.send_on_init = 0
        self.mask = 0
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
        if not isinstance(name, str):
            raise TypeError(f'Expected str but got {type(name)}')
        try:
            _ = self.__name
        except AttributeError:
            self.__name = name
        else:
            raise AssertionError('can\'t set attribute')

    @property
    def msg(self):
        """A reference to the message containing this signal."""
        return self.__msg

    @msg.setter
    def msg(self, msg):
        """Add a reference to message this signal is included in."""
        if msg is not None and not isinstance(msg, Message):
            raise TypeError(f'Expected {Message} but got {type(msg)}')
        self.__msg = msg

    @property
    def raw_val(self):
        """Return the numeric value of this signal."""
        raw_val = (self.__val >> self.bit_start) * self.scale + self.offset
        # Check if raw_val should be negative
        if raw_val > 0 and self.min_val < 0:
            bval = '{:b}'.format(int(raw_val))
            if bval[0] == '1' and len(bval) == self.bit_len:
                raw_val = float(-self._twos_complement(int(raw_val)))
        return int(raw_val)

    @property
    def value(self):
        """Get the signal value.

        Returns:
            The named signal value if it exists, otherwise the same as raw_val.
        """
        curr_val = self.raw_val
        if self.values:
            for key, val in self.values.items():
                if val == curr_val:
                    curr_val = key
                    break
            else:
                raise ValueError(f'{self}.raw_value is set to {self.raw_val} '
                                 f'which is not in {self.values}')
        return curr_val

    @value.setter
    def value(self, value):
        """Set the signal value based on the offset and scale."""
        negative = False

        # self.values will only be set if the signal has a discrete set of
        # values, otherwise the signal will be defined with min_val and max_val
        if self.values:
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
        if size > self.bit_len:
            raise ValueError('Unable to set {} to  {}; value too large!'
                             ''.format(self.name, num))

        if negative:
            num = self._twos_complement(num)

        self.__val = num << self.bit_start

    def _twos_complement(self, num):
        """Return the twos complement value of a number."""
        # TODO: Switch to something like the line below
        # pv_val = int('{:b}'.format(abs(int(pv_val) - (1 << pv_len)))[-pv_len:], 2)
        tmp = '{:b}'.format(num)
        tmp = tmp.replace('0', '2')
        tmp = tmp.replace('1', '0')
        tmp = tmp.replace('2', '1')

        while len(tmp) < self.bit_len:
            tmp = '1' + tmp
        return int(tmp, 2) + 1

    def set_mask(self):
        """Set the signal mask based on bit_start and bit_len."""
        if self.bit_start < 0:
            raise ValueError(f'{self}.bit_start is negative!')
        try:
            self.mask = 2 ** self.bit_len - 1 << self.bit_start
        except ValueError:
            print(self.bit_len, self.bit_start)

    def pprint(self, short_name=False, value=False):
        """Print colored info abnout the signal to stdout."""
        colorama_init()
        color = Fore.CYAN + Style.BRIGHT
        rst = Fore.RESET + Style.RESET_ALL
        if not short_name and not self.long_name:
            short_name = True
        if short_name:
            name = self.name
        else:
            name = self.long_name
        print('{} - Signal: {}'.format(color, name))
        if self.values.keys():
            if value:
                print('            ^- {}{}'.format(self.value, rst))
            else:
                print('            ^- [')
                multiple = False
                for key, val in self.values.items():
                    if multiple:
                        print(', ')
                    print('{}({})'.format(key, hex(val)))
                    multiple = True
                print(']{}\n'.format(rst))
        else:
            if value:
                print('            ^- {}{}{}'.format(self.value, self.units,
                                                     rst))
            else:
                print('            ^- [{} : {}]{}'.format(self.min_val,
                                                          self.max_val, rst))
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
