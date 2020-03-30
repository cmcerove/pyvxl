#!/usr/bin/env python

"""Types used by pyvxl."""

from os import path
from pydbc import DBCParser


class Channel:
    """A CAN or LIN channel."""

    def __init__(self, num=0, name='', baud=500000, protocol='CAN'):  # noqa
        self.num = num
        self.name = name
        self.baud = baud
        self.protocol = protocol
        self.__connected = False

    def __str__(self):
        """Return a string representation of this channel."""
        return (f'Channel({self.num}, {self.name}, {self.baud}, '
                f'{self.protocol})')

    def connect(self):
        """Connect to the channel."""
        if self.connected:
            raise AssertionError(f'{self} is already connected')
        self.__connected = True

    def disconnect(self):
        """Disconnect from the channel."""
        if not self.connected:
            raise AssertionError(f'{self} is already disconnected')
        self.__connected = False

    @property
    def connected(self):
        """Whether the channel is connected."""
        return self.__connected

    @property
    def num(self):
        """The numeric value of this channel."""
        return self.__num

    @num.setter
    def num(self, num):
        """Set the channel number."""
        if not isinstance(num, int):
            raise TypeError(f'Expected int, got {type(num)}')


class Database:
    """An imported database."""

    def __init__(self, db_path): # noqa
        self.__nodes = {}
        self.__messages = {}
        self.__messages_by_id = {}
        self.__signals = {}
        self.__db_path = None

    @property
    def db(self):
        """Return the imported database path if imported, otherwise None."""
        return self.__db_path

    @db.setter
    def db(self, db):
        """Import a database."""
        if not isinstance(db, str):
            raise TypeError(f'Expected str but got {type(db)}')
        if not path.isfile(db):
            raise ValueError(f'Database {db} does not exist')
        _, ext = path.splitext(db)
        # TODO: Implement .arxml import
        supported = ['.dbc']
        if ext not in supported:
            raise TypeError(f'{db} is not supported. Supported file types: '
                            f'{supported}')
        if ext == '.dbc':
            self.__import_dbc(db)

    def __import_dbc(self, db):
        """Import a dbc."""
        with open(db, 'r') as f:
            dbc = f.read()

        self.__db_path = db
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
