#!/usr/bin/env python

"""CAN types used by pyvxl.CAN."""

from os import path
from pyvxl.pydbc import DBCParser
from colorama import Fore, Back, Style
from colorama import init as colorama_init
from colorama import deinit as colorama_deinit


class Database:
    """A CAN database."""

    def __init__(self, db_path): # noqa
        self.__nodes = {}
        self.__messages = {}
        self.__messages_by_id = {}
        self.__signals = {}
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
        with open(db, 'r') as f:
            dbc = f.read()

        self.__path = db
        p = DBCParser(self, write_tables=0, debug=False)
        p.parse(dbc)
        if not p.dbc.messages:
            raise ValueError('{} contains no messages or is not a valid dbc.'
                             ''.format(db))
        msbMap = {}
        for x in range(1, 9):
            littleEndian = 0
            bigEndian = (x - 1) * 8
            ret = {}
            for i in range(x / 2 * 8):
                ret[bigEndian] = littleEndian
                ret[littleEndian] = bigEndian
                littleEndian += 1
                bigEndian += 1
                if bigEndian % 8 == 0:
                    bigEndian -= 16
        msbMap[x] = ret

        for msg in p.dbc.messages.values():

            if msg.send_type_num is not None and\
               msg.send_type_num < len(p.send_types):
                msg.send_type = p.send_types[msg.send_type_num]

            setendianness = False
            for sig in msg.signals:
                if not setendianness:
                    if msg.id > 0xFFFF:
                        if msg.sender.lower() in p.dbc.nodes:
                            sender = p.dbc.nodes[msg.sender.lower()].source_id
                            if (sender & 0xF00) > 0:
                                print(msg.name)
                            msg.id = (msg.id & 0xFFFF000) | 0x10000000 | sender
                        else:
                            print(msg.sender, msg.name)
                    msg.endianness = sig.endianness
                    setendianness = True
                if msg.dlc > 0:
                    try:
                        sig.bit_start = msbMap[msg.dlc][sig.bit_msb] - (sig.bit_len-1)
                    except KeyError:  # This only happens when the msb doesn't change
                        sig.bit_start = sig.bit_msb - (sig.bit_len - 1)
                    sig.set_mask()
                    if sig.init_val is not None:
                        sig.set_val(sig.init_val * sig.scale + sig.offset)
        return p.dbc

    @property
    def nodes(self):
        """A dictionary of imported nodes."""
        return self.__nodes

    @nodes.setter
    def nodes(self, node):
        """Add a node to the dictionary."""
        if not isinstance(node, Node):
            raise TypeError(f'Expected {Node} but got {type(node)}')
        self.__nodes[node.name] = node

    def get_node(self, name):
        """Get a node by name."""
        pass

    def find_node(self, name):
        """Find nodes by name."""

    @property
    def messages(self):
        """A dictionary of imported messages stored by message name."""
        return self.__messages

    @messages.setter
    def messages(self, msg):
        """Add a message to the dictionary."""
        if not isinstance(msg, Message):
            raise TypeError(f'Expected {Message} but got {type(msg)}')
        if msg.name in self.__messages:
            old_msg = self.__messages.pop(msg.name)
            self.__messages_by_id.pop(old_msg)
        if msg.id in self.__messages:
            old_msg = self.__messages_by_id.pop(msg.name)
            self.__messages.pop(old_msg)
        self.__messages[msg.name] = msg
        self.__messages_by_id[msg.id] = msg

    @property
    def message_ids(self):
        """A dictionary of imported messages stored by id."""
        return self.__messages_by_id

    def get_message(self, name_or_id):
        """Get a message by name or id."""
        pass
        '''
        if self.
        msg = None
        for msg in self.
        '''

    def find_message(self, name_or_id, exact=False):
        """Find messages by name or id.

        Returns a list of message objects.
        """
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


class Node:
    """A CAN node."""

    def __init__(self, name):  # noqa
        self.name = name

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

    def __init__(self, name):  # noqa
        self.name = name

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

    def __init__(self, name):  # noqa
        self.name = name

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
