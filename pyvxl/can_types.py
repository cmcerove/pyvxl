#!/usr/bin/env python

"""Types used by pyvxl."""

from os import path
from pyvxl.pydbc import DBCParser
from pyvxl.vxl import VxlCan, VxlChannel


class Channel(VxlChannel):
    """A named transmit only extension of VxlChannel adding databases."""

    def __init__(self, name, num=0, baud=500000, db=''):  # noqa
        self.name = name
        # Minimum queue size since we won't be receiving
        self.__vxl = VxlCan(num, baud, rx_queue_size=16)
        self.db = db

    def __str__(self):
        """Return a string representation of this channel."""
        return (f'Channel({self.num}, {self.baud}, {self.name})')

    @property
    def name(self):
        """The name of the channel."""
        return self.__name

    @name.setter
    def name(self, name):
        """Set the name of the channel."""
        if not isinstance(name, str):
            raise TypeError('Expected str, but got {}'.format(type(name)))
        self.__name = name

    @property
    def db(self):
        """The database for this channel."""
        return self.__db

    @db.setter
    def db(self, db_path):
        """Set the database for this channel."""
        self.__db = None
        if db_path:
            self.__db = Database(db_path)

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
        return self._send(msg, send_once)

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


class Database:
    """."""

    def __init__(self, db_path): # noqa
        self.__nodes = {}
        self.__messages = {}
        self.__messages_by_id = {}
        self.__signals = {}
        self.path = db_path

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
            self.__import_dbc(db)

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
        if self.
        msg = None
        for msg in self.

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

    if msg.send_type_num is not None and\
       msg.send_type_num < len(p.send_types):
        msg.send_type = p.send_types[msg.send_type_num]
    pass

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

