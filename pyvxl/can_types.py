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

    def get_message(self, name_or_id):
        """Get a message by name or id."""
        if self.
        msg = None
        for msg in self.

    def find_message(self, name_or_id, exact=False):
        """Find messages by name or id.

        Returns a list of message objects.
        """
        pass

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
