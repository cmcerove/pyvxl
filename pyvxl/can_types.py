#!/usr/bin/env python3

"""CAN types used by pyvxl.CAN."""

import logging
from math import ceil
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

        for msg in p.messages.values():
            if msg.send_type_num is not None and\
               msg.send_type_num < len(p.send_types):
                msg.send_type = p.send_types[msg.send_type_num]

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
        dlc = ceil(len(data) / 2)
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
                                 f'in {self}')
        elif isinstance(name_or_id, int):
            # Strip the extended ID bit if it exists
            name_or_id &= 0x1fffffff
            if name_or_id not in self.messages:
                raise ValueError(f'0x{name_or_id:X} does not match a message '
                                 f'id in {self}')
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
            signal = self.signals[name.lower()]
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
        self.long_name = None
        self.dlc = length
        self.sender = sender
        self.signals = signals
        self.__sending = False
        self.period = 0
        self.delay = None
        self.send_type_num = None
        self.send_type = None
        self.repetitions = None
        self.update_func = None
        # TODO: Populate this on import
        self.transmitters = None
        self.__init_completed = True

    def __str__(self):
        """Return a string representation of this message."""
        string = f'Message(0x{self.id:X}, {self.name}) - 0x{self.data}'
        if self.signals:
            sig_strs = [str(sig) for sig in self.signals]
            string += '\n - {}'.format('\n - '.join(sig_strs))
        return string

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
    def signals(self):
        """The signals within this message."""
        return self.__signals

    @signals.setter
    def signals(self, signals):
        """Add all signals to this message."""
        if not isinstance(signals, list):
            raise TypeError(f'Expected list but got {type(signals)}')
        try:
            _ = self.__signals
        except AttributeError:
            pass
        else:
            raise AssertionError('can\'t set attribute')

        mask_check = 0
        added_signals = []
        for sig in signals:
            if not isinstance(sig, Signal):
                raise TypeError(f'Expected Signal but got {type(sig)}')
            sig.msg = self
            # Make sure no signals overlap
            if mask_check & sig.mask == 0:
                mask_check |= sig.mask
                added_signals.append(sig)
            else:
                for added_sig in added_signals:
                    if added_sig.mask & sig.mask != 0:
                        raise AssertionError(f'{added_sig} and {sig} overlap')

        self.__signals = signals
        if not self.__signals:
            self.data = 0

    @property
    def data(self):
        """An up to 64 bit int of all signal data.

        This value is always returned in big endian format since that's how
        it will be transmitted on the bus.
        """
        data = 0
        if self.signals:
            for sig in self.signals:
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
                sig.raw_val = data
            if int(self.data, 16) != data:
                raise ValueError(f'One or more values in {data:X} do not map '
                                 'to valid signal values for:\n'f'{self}')
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
        if self.sending:
            raise AssertionError(f'Stop sending {self} before changing the '
                                 'period')
        self.__period = period

    @property
    def sending(self):
        """True if the message is currently being sent by the tx thread."""
        return self.__sending

    def _set_sending(self, value):
        """True if the message is currently being sent by the tx thread.

        This is meant to be an internal function for pyvxl only. If you
        call this function externally, make sure you are aware of the problems
        you can create.
        """
        if not isinstance(value, bool):
            raise TypeError(f'Expected bool but got {type(value)}')
        self.__sending = value

    def pprint(self):
        """Print colored info about the message to stdout."""

        colorama_init()
        print('')
        color = Style.BRIGHT + Fore.GREEN
        data = self.data
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


def gen_msb_map():
    """Generate dictionary to look up the start bit for each signal."""
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
    return msb_map


class Signal:
    """A CAN signal."""

    __msb_map = gen_msb_map()

    def __init__(self, name, mux, bit_msb, bit_len, endianness, signedness,
                 scale, offset, min_val, max_val, units, receivers):  # noqa
        self.name = name
        self.mux = mux  # not implemented
        self.endianness = endianness
        self.__bit_msb = bit_msb if self.endianness == 'big' else bit_msb + 7
        self.__bit_start = bit_msb
        self.bit_len = bit_len
        self.__signed = bool(signedness == '-')
        self.scale = scale
        self.offset = offset
        self.min_val = min_val
        self.max_val = max_val
        self.units = units
        self.receivers = receivers
        self.long_name = ''
        self.values = {}
        self.__val = 0
        self.init_val = None
        self.send_on_init = 0
        self.__msg = None

    def __str__(self):
        """Return a string representation of this database."""
        if isinstance(self.val, str) or isinstance(self.val, float):
            string = f'Signal({self.name}) = {self.val}'
        else:
            string = f'Signal({self.name}) = {self.val:X}'
        return string

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
    def endianness(self):
        """The endianness of the signal."""
        return self.__endianness

    @endianness.setter
    def endianness(self, endianness):
        """The endianness of the signal."""
        if not isinstance(endianness, int):
            raise TypeError(f'Expected int but got {type(endianness)}')
        if endianness not in [0, 1]:
            raise ValueError(f'{endianness} must be 0 or 1')
        try:
            _ = self.__endianness
        except AttributeError:
            self.__endianness = 'big' if endianness == 0 else 'little'
        else:
            raise AssertionError('can\'t set attribute')

    @property
    def signed(self):
        """Return true if this signal is signed instead of unsigned."""
        return self.__signed

    @property
    def msg(self):
        """A reference to the message containing this signal."""
        return self.__msg

    @msg.setter
    def msg(self, msg):
        """Add a reference to message this signal is included in."""
        if self.__msg is not None:
            raise AttributeError('can\'t set attribute')
        if not isinstance(msg, Message):
            raise TypeError(f'Expected {Message} but got {type(msg)}')
        msb_map = Signal.__msb_map
        if msg.dlc in msb_map and self.__bit_msb in msb_map[msg.dlc]:
            self.__bit_start = Signal.__msb_map[msg.dlc][self.__bit_msb]
        self.__bit_start -= self.bit_len - 1
        self.__mask = 2 ** self.bit_len - 1 << self.__bit_start
        self.__msg = msg

    @property
    def bit_start(self):
        """The start bit of the signal within the full message."""
        if self.__msg is None:
            raise AssertionError('bit_start is not valid since there is no '
                                 'message associated with this signal')
        return self.__bit_start

    @property
    def mask(self):
        """The bit mask for this signal relative to the complete message."""
        if self.__msg is None:
            raise AssertionError('mask is not valid since there is no '
                                 'message associated with this signal')
        return self.__mask

    @property
    def raw_val(self):
        """The signal value as it would look within the full message data."""
        return self.__val

    @raw_val.setter
    def raw_val(self, msg_data):
        """Set the raw_value based on the full message data."""
        if not isinstance(msg_data, int):
            raise TypeError(f'Expected int but got {type(msg_data)}')
        self.__val = msg_data & self.mask

    @property
    def num_val(self):
        """Return the numeric value of this signal."""
        num_val = self.__val >> self.bit_start
        if self.endianness == 'little':
            num_bytes = ceil(self.bit_len / 8)
            tmp = num_val.to_bytes(num_bytes, 'little', signed=self.signed)
            num_val = int.from_bytes(tmp, 'big', signed=self.signed)
        num_val = num_val * self.scale + self.offset
        # Check if num_val should be negative
        if num_val > 0 and self.min_val < 0:
            bval = '{:b}'.format(int(num_val))
            if bval[0] == '1' and len(bval) == self.bit_len:
                num_val = float(-self._twos_complement(int(num_val)))
        return round(num_val, 4)

    @property
    def val(self):
        """Get the signal value.

        Returns:
            The named signal value if it exists, otherwise same as num_val.
        """
        curr_val = self.num_val
        if self.values:
            curr_val = int(curr_val)
            for key, val in self.values.items():
                if val == curr_val:
                    curr_val = key
                    break
            else:
                raise ValueError(f'{self.name}.num_val is set to '
                                 f'{self.num_val} which is not in '
                                 f'{self.values}')
        return curr_val

    @val.setter
    def val(self, value):
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

        num = int((float(num) - float(self.offset)) / float(self.scale))

        if num < 0:
            num = abs(num)
            negative = True

        size = len('{:b}'.format(num))
        if size > self.bit_len:
            raise ValueError('Unable to set {} to {}; value too large!'

                             ''.format(self.name, num))

        if negative:
            num = self._twos_complement(num)

        # Swap the byte order if necessary
        if self.endianness == 'little':
            num_bytes = ceil(self.bit_len / 8)
            tmp = num.to_bytes(num_bytes, 'little', signed=self.signed)
            num = int.from_bytes(tmp, 'big', signed=self.signed)
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
