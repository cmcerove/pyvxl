#!/usr/bin/env python

"""CAN types used by pyvxl.CAN."""

import logging
from math import ceil
from os import path
from sys import exit, argv
from pyvxl.pydbc import DBCParser
from colorama import Fore, Back, Style
from colorama import init as colorama_init
from colorama import deinit as colorama_deinit
from decimal import Decimal


class Database:
    """A CAN database."""

    def __init__(self, db_path): # noqa
        self.__nodes = {}
        self.__messages = {}
        self.__signals = {}
        self.__protocol = 'CAN'
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
            raise ValueError(f'{db} contains no messages.')

        self.__nodes = p.nodes
        self.__messages = p.messages
        self.__signals = p.signals

        can_fd = False
        if p.can_fd_support:
            self.__protocol = 'CAN FD'
            can_fd = True

        # Set the id_type on each message in case the dbc did not specify it
        # for all messages. DBCs that are only standard CAN won't include the
        # id_type.
        for msg in p.messages.values():
            if msg.id_type is None:
                if not can_fd and msg.id <= 0x7FF:
                    msg.id_type = 'CAN Standard'
                elif not can_fd and msg.id > 0x7FF:
                    msg.id_type = 'CAN Extended'
                elif can_fd and msg.id <= 0x7FF:
                    msg.id_type = 'CAN FD Standard'
                else:  # can_fd and msg.id > 0x7FF:
                    msg.id_type = 'CAN FD Extended'

    @property
    def protocol(self):
        """Whether this database requires CAN or CAN FD."""
        return self.__protocol

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
        elif isinstance(name_or_id, int) and not isinstance(name_or_id, bool):
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
        num_found = 0
        msg_id = self._check_message(name)
        if isinstance(msg_id, int) and not isinstance(msg_id, bool):
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
            signals = self.signals[name.lower()]
            if len(signals) == 1:
                signal = signals[0]
            else:
                signal = signals
        else:
            for signals in self.signals.values():
                for sig in signals:
                    if name.lower() == sig.long_name:
                        signal = sig
                        break
                if signal is not None:
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
        self.__brs = False
        self.period = 0
        self.delay = None
        self.repetitions = None
        self.update_func = None
        self.__id_type = None
        # TODO: Populate this on import
        self.transmitters = None
        self.__init_completed = True
        self.__valid_fd_dlcs = list(range(9)) + [12, 16, 20, 24, 32, 48, 64]

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
    def id_type(self):
        """The ID type for this message.

        Indicates whether this message is CAN Standard, CAN Extended,
        CAN FD Standard or CAN FD Extended.
        """
        return self.__id_type

    @id_type.setter
    def id_type(self, id_type):
        """."""
        id_types = {0: 'CAN Standard', 1: 'CAN Extended',
                    14: 'CAN FD Standard', 15: 'CAN FD Extended'}
        if isinstance(id_type, str):
            for id_type_val, id_type_name in id_types.items():
                if id_type == id_type_name:
                    id_type = id_type_val
                    break
            else:
                raise ValueError(f'{id_type} is an invalid id_type or pyvxl '
                                 'has not been updated to handle this case. '
                                 f'Implemented id_types = {id_types.values()}')
        elif not isinstance(id_type, int) or isinstance(id_type, bool):
            raise TypeError(f'Expected int or str but got {type(id_type)}')
        elif id_type not in id_types:
            raise ValueError(f'{id_type} is an invalid id_type or pyvxl has '
                             'not been updated to handle this case. '
                             f'Implemented id_types = {id_types}')
        can_fd = bool(id_type & 0b1110)
        if can_fd and self.dlc not in self.__valid_fd_dlcs:
            raise ValueError(f'Msg: {self.name}, DLC: {self.dlc}\n CAN FD '
                             f'dlc must be {self.__valid_fd_dlcs}')
        elif not can_fd and (self.dlc < 0 or self.dlc > 8):
            raise ValueError(f'{self.dlc}: CAN dlc must be between 0 and 8')
        self.__id_type = id_type

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
        if not isinstance(dlc, int) or isinstance(dlc, bool):
            raise TypeError(f'Expected int but got {type(dlc)}')
        elif dlc < 0 or dlc > 64:
            raise ValueError(f'{dlc} must be between 0 and 64')
        elif dlc > 8 and dlc not in [12, 16, 20, 24, 32, 48, 64]:
            raise ValueError(f'Msg: {self.name}, DLC: {self.dlc}\n CAN FD '
                             f'dlc must be {self.__valid_fd_dlcs}')
        self.__dlc = dlc
        self.__max_val = int('FF' * dlc, 16)

    @property
    def signals(self):
        """The signals within this message."""
        return self.__signals

    @signals.setter
    def signals(self, signals):
        """Add all signals to this message."""
        if not isinstance(signals, list):
            raise TypeError(f'Expected list but got {type(signals)}')

        mask_check = 0
        added_signals = []
        for sig in signals:
            if not isinstance(sig, Signal):
                raise TypeError(f'Expected Signal but got {type(sig)}')
            sig.msg = self
            # Make sure no signals overlap
            if mask_check & sig.mask == 0:
                mask_check |= sig.mask
                if sig.name in added_signals:
                    logging.warning(f'{sig.name} is duplicated in message '
                                    f'{self.name}. Signal attributes like the '
                                    'initial value or long name might be '
                                    'incorrect since the dbc format only '
                                    'stores attributes by signal name and '
                                    'message ID.')
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
                data |= sig.msg_val
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
        elif not isinstance(data, int) or isinstance(data, bool):
            raise TypeError(f'Expected a hex str or int but got {type(data)}')
        if data < 0 or data > self.__max_val:
            raise ValueError(f'{data:X} must be positive and less than the '
                             f'maximum value of {self.__max_val:X}!')
        if self.signals:
            for sig in self.signals:
                sig.msg_val = data
        else:
            self.__data = data

    @property
    def period(self):
        """The transmit period of the message in milliseconds."""
        return self.__period

    @period.setter
    def period(self, period):
        """Set the transmit period for the message."""
        if not isinstance(period, int) or isinstance(period, bool):
            raise TypeError(f'Expected int but got {type(period)}')
        if self.sending:
            raise AssertionError(f'Stop sending {self} before changing the '
                                 'period')
        self.__period = period

    @property
    def sending(self):
        """True if the message is currently being sent by the tx thread."""
        return self.__sending

    @property
    def brs(self):
        """Whether the BRS bit is enabled on this message.

        When BRS is enabled, the data portion of the message will be
        transmitted at a higher baud rate.
        """
        return self.__brs

    @brs.setter
    def brs(self, brs):
        """Enable or disable the BRS bit for this message."""
        if not isinstance(brs, bool):
            raise TypeError(f'Expected bool but got {type(brs)}')
        self.__brs = brs

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
    # CAN FD can have DLCs up to 64 bytes
    max_dlc = 64
    for x in range(1, max_dlc + 1):
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

    def __init__(self, name, mux, bit_msb, bit_len, endianness, signedness,  # noqa
                 scale, offset, min_val, max_val, units, receivers):  # noqa
        self.values = {}
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
        if not isinstance(endianness, int) or isinstance(endianness, bool):
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
        """Add a reference to the message containing this signal."""
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
    def values(self):
        """A dictionary mapping numeric values to names."""
        return self.__values_by_name

    @values.setter
    def values(self, val_dict):
        """Set the values dictionary."""
        if not isinstance(val_dict, dict):
            raise TypeError(f'Expected dict but got {type(val_dict)}')
        invalid_keys = []
        invalid_vals = []
        for key, val in val_dict.items():
            if not isinstance(key, str):
                invalid_keys.append(key)
            if not isinstance(val, int) or isinstance(val, bool):
                invalid_vals.append(val)
        if invalid_keys or invalid_vals:
            error = ''
            if invalid_keys:
                error += f'Keys must be strings. Invalid keys = {invalid_keys}'
            if invalid_vals:
                if error:
                    error += '\n'
                error += ('Values must be integers. Invalid values = '
                          f'{invalid_vals}')

            raise TypeError(error)
        self.__values_by_name = val_dict
        self.__values_by_num = dict((v, k) for k, v in val_dict.items())

    @property
    def min_val(self):
        """The minimum scaled value for this signal."""
        return self.__min_val

    @min_val.setter
    def min_val(self, min_val):
        """Set the minimum scaled value for this signal."""
        if not isinstance(min_val, (int, float)) or isinstance(min_val, bool):
            raise TypeError(f'Expected int or float but got {type(min_val)}')

        if self.signed:
            bit_len = self.bit_len - 1
            max_positive = self._scale(int('0' + ('1' * bit_len), 2))
            max_negative = self._scale(int('1' + ('0' * bit_len), 2))
            all_bits = min(max_positive, max_negative)
        else:
            all_bits = self._scale(int('1' * self.bit_len, 2))

        no_bits = self._scale(0)
        min_possible = min(all_bits, no_bits)

        if min_val > min_possible:
            min_val = min_possible

        # Make sure the value is transmitable on CAN by unscaling and scaling
        self.__min_val = self._scale(self._unscale(Decimal(str(min_val))))

    @property
    def max_val(self):
        """The maximum scaled value for this signal."""
        return self.__max_val

    @max_val.setter
    def max_val(self, max_val):
        """Set the maximum scaled value for this signal."""
        if not isinstance(max_val, (int, float)) or isinstance(max_val, bool):
            raise TypeError(f'Expected int or float but got {type(max_val)}')

        if self.signed:
            bit_len = self.bit_len - 1
            max_positive = self._scale(int('0' + ('1' * bit_len), 2))
            max_negative = self._scale(int('1' + ('0' * bit_len), 2))
            all_bits = max(max_positive, max_negative)
        else:
            all_bits = self._scale(int('1' * self.bit_len, 2))

        no_bits = self._scale(0)
        max_possible = max(all_bits, no_bits)

        if max_val > max_possible:
            max_val = max_possible

        # Make sure the value is transmitable on CAN by unscaling and scaling
        self.__max_val = self._scale(self._unscale(Decimal(str(max_val))))

    @property
    def msg_val(self):
        """The signal value as it would look within the full message data."""
        return self.__val

    @msg_val.setter
    def msg_val(self, msg_data):
        """Set the value based on the full message data."""
        if not isinstance(msg_data, int) or isinstance(msg_data, bool):
            raise TypeError(f'Expected int but got {type(msg_data)}')
        self.__val = msg_data & self.mask

    @property
    def raw_val(self):
        """The signal value as it would look within the full message data."""
        return self.msg_val >> self.bit_start

    @raw_val.setter
    def raw_val(self, raw_val):
        """Update msg_val with the new unscaled (ready for CAN) value."""
        self.msg_val = raw_val << self.bit_start

    @property
    def num_val(self):
        """The scaled numeric value of this signal."""
        return self._scale(self.raw_val)

    @property
    def val(self):
        """The named signal value if it exists, otherwise same as num_val."""
        if self.raw_val in self.__values_by_num:
            val = self.__values_by_num[self.raw_val]
        else:
            val = self.num_val
        return val

    @val.setter
    def val(self, val):
        """Set the signal value based on the offset and scale."""
        value_error = (f'{val} is invalid for {self.name}; valid values = '
                       f'{self.values}.')
        range_error = (f'Value {val} out of range! Valid range is '
                       f'{self.min_val} to {self.max_val} for signal '
                       f'{self.name}.')

        if isinstance(val, (float, int)):
            if val in self.__values_by_num:
                pass
            elif self.min_val <= val <= self.max_val:
                val = Decimal(str(val))
            elif self.values:
                raise ValueError(f'{value_error}\nAND\n{range_error}')
            else:
                raise ValueError(range_error)
        elif isinstance(val, str):
            if not self.values:
                raise ValueError(value_error)
            # val.lower() to make this case insensitive
            lower_vals = dict((val.lower(), val) for val in self.values)
            if val.lower() in lower_vals:
                val = self.values[lower_vals[val.lower()]]
            else:
                raise ValueError(value_error)

        else:
            raise TypeError(f'Expected str, int or float but got {type(val)}')

        self.raw_val = self._unscale(val)

    def _scale(self, val):
        """Scale a number based on the other attributes in this signal."""
        if self.endianness == 'little':
            num_bytes = ceil(self.bit_len / 8)
            tmp = val.to_bytes(num_bytes, 'little', signed=self.signed)
            val = int.from_bytes(tmp, 'big', signed=self.signed)

        scale = Decimal(str(self.scale))
        offset = Decimal(str(self.offset))
        val = Decimal(str(val)) * scale + offset

        if int(val) == val:
            val = int(val)
        else:
            val = float(val)
        return val

    def _unscale(self, val):
        """Convert a scaled number to unscaled. The opposite of _scale."""
        # Only values that aren't named should be scaled i.e. not in the
        # Value Descriptions tab for a signal in the CANdb++ Editor.
        if isinstance(val, Decimal) and self.scale != 0:
            offset = Decimal(str(self.offset))
            scale = Decimal(str((self.scale)))
            val = int((val - offset) / scale)
        else:
            val = int(val)

        if val < 0:
            # Convert to positive so bit_len and other math works below
            val = abs(val)
            negative = True
        else:
            negative = False

        if len(f'{val:b}') > self.bit_len:
            raise ValueError(f'Unable to set {self.name} to {val}; value too '
                             'large!')
        if negative:
            val = self._twos_complement(val)

        # Swap the byte order if necessary
        if self.endianness == 'little':
            num_bytes = ceil(self.bit_len / 8)
            tmp = val.to_bytes(num_bytes, 'little', signed=self.signed)
            val = int.from_bytes(tmp, 'big', signed=self.signed)
        return val

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
Imported
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
