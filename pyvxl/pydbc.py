#!/usr/bin/env python
"""
Vector DBC file parser. Based on the DBC file parser part of
http://sourceforge.net/projects/cantools/ .

Usage:

    pydbc.py <DBC file specification>

Regerences:
    http://www.dabeaz.com/ply/ply.html
    http://www.dabeaz.com/ply/PLYTalk.pdf
"""

import sys, logging
from binascii import unhexlify
import ply.lex as lex
import ply.yacc as yacc


class DBCFile(object):
    """DBC file object."""

    def __init__(self):
        """."""
        self.periodics = []
        self.version = None
        self.symbols = None
        self.nodes = None
        self.messages = None
        self.envvars = None
        self.attributes = None
        self.signals = None
        self.signalsByName = None


class DBCNode(object):
    """DBC node object."""

    def __init__(self, name):
        """."""
        self.name = name
        self.sourceID = 0
        self.ecuID = 0
        self.txMessages = []
        self.rxMessages = []


class DBCMessage(object):
    """DBC message object."""

    def __init__(self, msgid, name, length, sender, signals):
        """."""
        self.id = int(msgid)
        self.dlc = length
        self.__data = 0
        self.data = 0
        self.endianness = 0
        self.name = str(name)
        self.sender = str(sender)
        self.signals = signals
        for signal in signals:
            signal.add_msg_ref(self)
        self.period = 0
        self.delay = None
        self.send_type_num = None
        self.send_type = None
        self.repetitions = None
        self.sending = False
        self.update_func = None

        # TODO: delete these three below after making sure they aren't used
        self.comment = ''
        self.attributes = None
        self.transmitters = None

    def get_data(self):
        """Get the current message data based on each signal value.

        Returns a the current message data as a hexadecimal string
        padded with zeros to the message length.
        """
        # TODO: switch to __data
        # data = self.__data
        return '{:0{}X}'.format(self.data, self.dlc * 2)

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
                                     ' string {}!'.format(data))
            if isinstance(data, int) or isinstance(data, long):
                # Check for invalid length
                if len('{:X}'.format(data)) > (self.dlc * 2):
                    raise ValueError('{:X} is longer than message length of {}'
                                     ' bytes'.format(data, self.dlc))
            else:
                raise TypeError('Expected an int or str but got {}'.format(type(data)))
                # Handling for messages without signals
            for sig in self.signals:
                sig.val = data & sig.mask
            self.update_data()
        else:
            logging.error('set_data called with no data!')

    def update_data(self):
        """Update the message data based on signal values."""
        # data = self.__data
        data = self.data
        for sig in self.signals:
            # Clear the signal value in data
            data &= ~sig.mask
            # Set the value
            data |= sig.val
        self.data = data


class DBCSignal(object):
    """DBC signal object."""

    def __init__(self, name, mux, bit_msb, bit_len, endianness, signedness,
                 scale, offset, min_val, max_val, units, receivers):
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
        self.fullName = ''
        self.values = {}
        self.msg_id = 0
        self.val = 0
        self.initVal = None
        self.sendOnInit = 0
        self.mask = 0
        self.bit_start = 0
        self.msg = None

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
        self.msg.update_data()
        return True

    def get_val(self, raw=False):
        """Get the signal's value.

        Args:
            raw: If True, always returns the numeric value of the signal.
        """
        tmp = self.val >> self.bit_start
        curr_val = (tmp * self.scale + self.offset)
        # Check if curr_val is really supposed to be negative
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
            print(self.name)
        self.mask = pow(2, self.bit_len) - 1 << self.bit_start


class DBCEnvVar(object):
    """DBC environmental variable object."""

    def __init__(self, name, etype, minV, maxV, unit, initial, index, access,
                 nodes=None, vals=None, comment=""):
        """."""
        self.name = str(name)
        self.type = int(etype)
        self.min = float(minV)
        self.max = float(maxV)
        self.unit = str(unit)
        self.initial = float(initial)
        self.index = int(index)
        self.access = int(access)
        self.nodes = nodes
        self.vals = vals
        self.comment = str(comment)

    def __str__(self):
        one = "{name:%s, type:%d, min:%f, max:%f," % (self.name, self.type,
                                                      self.min, self.max)
        two = "unit:%s, initial:%f, index:%d, access:%d," % (self.unit,
                                                             self.initial,
                                                             self.index,
                                                             self.access)
        return  one+two+" nodes:?, vals:?, comment:%s}" % (self.comment)

class DBCLexer(object):
    """DBC lexical analyzer object"""

    # Lexer token declaration
    tokens = ('VERSION', 'BO', 'BS', 'BU', 'SG', 'EV', 'SIG_VALTYPE', 'NS',
              'INT', 'FLOAT', 'NAN', 'STRING', 'ENUM', 'HEX', 'NS_DESC', 'CM',
              'BA_DEF', 'BA', 'VAL', 'CAT_DEF', 'CAT', 'FILTER', 'BA_DEF_DEF',
              'EV_DATA', 'ENVVAR_DATA', 'SGTYPE', 'SGTYPE_VAL', 'BA_DEF_SGTYPE',
              'BA_SGTYPE', 'SIG_TYPE_REF', 'VAL_TABLE', 'SIG_GROUP',
              'SIGTYPE_VALTYPE', 'BO_TX_BU', 'BA_DEF_REL', 'BA_REL',
              'BA_DEF_DEF_REL', 'BU_SG_REL', 'BU_EV_REL', 'BU_BO_REL',
              'SG_MUL_VAL', 'DUMMY_NODE_VECTOR', 'ID', 'STRING_VAL',
              'DOUBLE_VAL', 'INT_VAL')

    # Lexer token definition

    # Keywords
    reserved = {
        'VERSION':              'VERSION',
        'BO_':                  'BO',               # Botschaft (message)
        'BS_':                  'BS',
        'BU_':                  'BU',               # Steuergeraet (controller)
        'SG_':                  'SG',               # Signal
        'EV_':                  'EV',               # Environment
        'SIG_VALTYPE_':         'SIG_VALTYPE',
        'NS_':                  'NS',
        'INT':                  'INT',
        'FLOAT':                'FLOAT',
        'NAN':                  'NAN',
        'STRING':               'STRING',
        'ENUM':                 'ENUM',
        'HEX':                  'HEX',

        'NS_DESC_':             'NS_DESC',
        'CM_':                  'CM',                   # Comment
        'BA_DEF_':              'BA_DEF',               # Attribut-Definition
        'BA_':                  'BA',                   # Attribut
        'VAL_':                 'VAL',
        'CAT_DEF_':             'CAT_DEF',
        'CAT_':                 'CAT',
        'FILTER':               'FILTER',
        'BA_DEF_DEF_':          'BA_DEF_DEF',
        'EV_DATA_':             'EV_DATA',
        'ENVVAR_DATA_':         'ENVVAR_DATA',
        'SGTYPE_':              'SGTYPE',
        'SGTYPE_VAL_':          'SGTYPE_VAL',
        'BA_DEF_SGTYPE_':       'BA_DEF_SGTYPE',
        'BA_SGTYPE_':           'BA_SGTYPE',
        'SIG_TYPE_REF_':        'SIG_TYPE_REF',
        'VAL_TABLE_':           'VAL_TABLE',
        'SIG_GROUP_':           'SIG_GROUP',
        'SIGTYPE_VALTYPE_':     'SIGTYPE_VALTYPE',
        'BO_TX_BU_':            'BO_TX_BU',
        'BA_DEF_REL_':          'BA_DEF_REL',
        'BA_REL_':              'BA_REL',
        'BA_DEF_DEF_REL_':      'BA_DEF_DEF_REL',
        'BU_SG_REL_':           'BU_SG_REL',
        'BU_EV_REL_':           'BU_EV_REL',
        'BU_BO_REL_':           'BU_BO_REL',
        'SG_MUL_VAL_':          'SG_MUL_VAL',
    }

    # Ignored characters
    t_ignore = " \t\r"

    # Literal characters
    literals = ":;|,@+-[]()"

    # Lexer constructor
    def __init__(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    # Test it output
    def test(self, input): #pylint: disable=W0622
        self.lexer.input(input)
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            #print tok
            print(repr(tok.type), repr(tok.value))

    # Lexing error
    def t_error(self, t):
        print("Illegal character '%s' on line %d" % (t.value[0],
                                                     t.lexer.lineno))
        t.lexer.skip(1)

    # Dummy node vector
    def t_dummy_node_vector(self, t):
        #r'DUMMY_NODE_VECTOR[0-3]'
        r'DUMMY_NODE_VECTOR[0-9]+'
        t.value = int(t.value[17:])
        t.type = 'DUMMY_NODE_VECTOR'
        return t

    # Identifier
    def t_id(self, t):
        r'[a-zA-Z_][_a-zA-Z0-9]*'
        # Check for reserved identifiers
        t.type = self.reserved.get(t.value, 'ID')
        return t

    # String literal
    def t_string(self, t):
        r'\"([^"\\]|(\\.))*\"'
        if len(t.value) > 2:
            t.value = t.value[1:-1]
        else:
            t.value = ""
        t.type = 'STRING_VAL'
        return t

    # (Double precision) floating point number literal
    def t_double_val(self, t):
        r'[-+]?[0-9]+((\.[0-9]+([eE][-+]?[0-9]+)?)|([eE][-+]?[0-9]+))'
        t.value = float(t.value)
        t.type = 'DOUBLE_VAL'
        return t

    # Decimal integer number literal
    def t_decnumber(self, t):
        r'[-+]?[0-9]+'
        t.value = int(t.value)
        t.type = 'INT_VAL'
        return t

    # Hexadecimal integer number literal
    def t_hexnumber(self, t):
        r'0x[0-9a-fA-F]+'
        t.value = int(t.value, 16)
        t.type = 'INT_VAL'
        return t

    # New-line detection
    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += t.value.count('\n')

class DBCParser(object):
    """The main DBC parser object"""
    def __init__(self, lexer=None, **kwargs):
        self.dbc = DBCFile()
        self.signalDict = {}
        self.signalDictByName = {}
        self.send_types = []
        self.nodeDict = {}
        self.msgDict = {}
        if lexer:
            self.lexer = lexer
        else:
            self.lexer = DBCLexer()

        self.tokens = self.lexer.tokens
        self.parser = yacc.yacc(module=self, **kwargs)

    def parse(self, dbc):
        """Runs the dbc through the lexer"""
        if dbc:
            return self.parser.parse(dbc, self.lexer.lexer, 0, 0, None)
        else:
            return []


    # Parsing rules

    def p_error(self, p):
        """Prints a parsing error"""
        print("Syntax error at token %s (%s) on line %d" % (p.type, p.value,
                                                            p.lineno))
        #yacc.errok()

    # DBC file
    #########################################################################

    ###
    def p_dbc(self, p):
        '''dbc : version \
                 symbol_section \
                 message_section \
                 node_dict \
                 valtable_list \
                 message_dict \
                 message_transmitter_list \
                 envvar_list \
                 envvar_data_list \
                 comment_list \
                 attribute_definition_list \
                 attribute_definition_default_list \
                 attribute_list \
                 attribute_rel_list \
                 val_list \
                 sig_valtype_list \
                 signal_group_list'''
        self.dbc.version = p[1]
        self.dbc.symbols = p[2]
        # message_section - ignored
        self.dbc.nodes = self.nodeDict
        self.dbc.messages = p[6]
        self.dbc.envvars = p[8]
        self.dbc.attributes = p[13]
        # envvar_data_list - ignored
        self.dbc.signalsByName = self.signalDictByName
        self.dbc.signals = self.signalDict

    # Version
    #########################################################################

    ###
    def p_version(self, p):
        '''version : VERSION STRING_VAL'''
        p[0] = p[2]

    # Symbols
    #########################################################################

    ###
    def p_symbol_section(self, p):
        '''symbol_section : NS ':'
                          | NS ':' symbol_list'''
        if len(p) > 3 and len(p[3]) > 3:
            p[0] = p[3]
        else:
            p[0] = []

    ###
    def p_symbol_list(self, p):
        '''symbol_list : symbol
                       | symbol symbol_list'''
        if len(p) > 2:
            p[0] = p[2]
            p[0].insert(0, p[1])
        else:
            p[0] = [p[1]]

    ###
    def p_symbol(self, p):
        '''symbol : NS_DESC
                  | CM
                  | BA_DEF
                  | BA
                  | VAL
                  | CAT_DEF
                  | CAT
                  | FILTER
                  | BA_DEF_DEF
                  | EV_DATA
                  | ENVVAR_DATA
                  | SGTYPE
                  | SGTYPE_VAL
                  | BA_DEF_SGTYPE
                  | BA_SGTYPE
                  | SIG_TYPE_REF
                  | VAL_TABLE
                  | SIG_GROUP
                  | SIG_VALTYPE
                  | SIGTYPE_VALTYPE
                  | BO_TX_BU
                  | BA_DEF_REL
                  | BA_REL
                  | BA_DEF_DEF_REL
                  | BU_SG_REL
                  | BU_EV_REL
                  | BU_BO_REL
                  | SG_MUL_VAL'''
        p[0] = p[1]

    # Message section
    #########################################################################

    ###
    def p_message_section(self, p):
        '''message_section : BS ':' '''
        pass

    # Node list
    #########################################################################

    ###
    def p_space_node_dict(self, p):
        '''space_node_dict : empty
                           | ID space_node_dict'''
        if p[1]:
            p[0] = p[2]
            p[0][p[1].lower()] = DBCNode(p[1])
        else:
            p[0] = {}

    ###
    def p_node_dict(self, p):
        '''node_dict : BU ':' space_node_dict'''
        p[0] = p[3]
        self.nodeDict = p[3]

    # Valtable list
    #########################################################################

    def p_valtable_list(self, p):
        '''valtable_list : empty
                         | valtable valtable_list'''
        pass

    def p_valtable(self, p):
        '''valtable : VAL_TABLE ID val_map ';' '''
        pass

    # Message list
    #########################################################################

    ###
    def p_message_dict(self, p):
        '''message_dict : empty
                        | message message_dict'''
        if p[1]:
            p[0] = p[2]
            p[0][p[1].id] = p[1]
            if not self.nodeDict.has_key(p[1].sender.lower()):
                self.nodeDict[p[1].sender.lower()] = DBCNode(p[1].sender)
            self.nodeDict[p[1].sender.lower()].txMessages.append(p[1])
            self.msgDict = p[0]
        else:
            p[0] = {}

    def p_message(self, p):
        '''message : BO INT_VAL ID ':' INT_VAL ID signal_list'''
        p[0] = DBCMessage(p[2], p[3], p[5], p[6], p[7])
        for sig in p[7]:
            sig.msg_id = p[2]

    def p_signal_list(self, p):
        '''signal_list : empty
                       | signal signal_list'''
        if p[1]:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = []

    def p_signal(self, p):
        '''signal : SG signal_name mux_info ':' bit_start '|' bit_len '@' endianness signedness '(' scale ',' offset ')' '[' min '|' max ']' STRING_VAL comma_identifier_list'''
        p[0] = DBCSignal(p[2], p[3], p[5], p[7], p[9], p[10], p[12], p[14], p[17], p[19],
                         p[21], p[22])
        self.signalDict[p[2].lower()] = p[0]

    def p_envvar_list(self, p):
        '''envvar_list : empty
                       | envvar envvar_list'''
        if p[1]:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = []

    def p_envvar(self, p):
        '''envvar : EV ID ':' INT_VAL '[' double_val '|' double_val ']' \
                    STRING_VAL double_val INT_VAL DUMMY_NODE_VECTOR comma_identifier_list ';' '''
        p[0] = DBCEnvVar(p[2], p[4], p[6], p[8], p[10], p[11], p[12], p[13], p[14])

    def p_envvar_data_list(self, p):
        '''envvar_data_list : empty
                            | envvar_data envvar_data_list'''
        pass

    def p_envvar_data(self, p):
        '''envvar_data : ENVVAR_DATA ID ':' INT_VAL ';' '''
        pass

    def p_attribute_value(self, p):
        '''attribute_value : INT_VAL
                           | STRING_VAL
                           | DOUBLE_VAL'''
        p[0] = p[1]


    def p_attribute_list(self, p):
        '''attribute_list : empty
                          | attribute attribute_list'''
        if p[1]:
            p[0] = p[2]
            p[0][p[1][0]] = p[1][1]
        else:
            p[0] = {}

    def p_attribute(self, p):
        '''attribute : BA STRING_VAL attribute_value ';'
                     | BA STRING_VAL BU ID attribute_value ';'
                     | BA STRING_VAL BO INT_VAL attribute_value ';'
                     | BA STRING_VAL SG INT_VAL ID attribute_value ';'
                     | BA STRING_VAL EV ID attribute_value ';' '''
        if p[2] == 'SignalLongName':
            self.signalDict[p[5].lower()].fullName = p[6]
            self.signalDictByName[p[6].lower()] = self.signalDict[p[5].lower()]
        elif p[2] == 'GenSigStartValue':
            self.signalDict[p[5].lower()].initVal = p[6]
        elif p[2] == 'GenSigSendOnInit':
            self.signalDict[p[5].lower()].sendOnInit = p[6]
        elif p[2] == 'SourceId':
            self.nodeDict[p[4].lower()].sourceID = p[5]
        elif p[2] == 'GenMsgCycleTime':
            self.msgDict[p[4]].period = p[5]
        elif p[2] == 'GenMsgDelayTime':
            self.msgDict[p[4]].delay = p[5]
        elif p[2] == 'GenMsgSendType':
            # print('Setting send type for {:X} to {}'.format(p[4], p[5]))
            self.msgDict[p[4]].send_type_num = p[5]
        elif p[2] == 'GenMsgNrOfRepetitions':
            self.msgDict[p[4]].repetitions = p[5]

    def p_attribute_rel_list(self, p):
        '''attribute_rel_list : empty
                              | attribute_rel attribute_rel_list'''
        pass

    def p_attribute_rel(self, p):
        '''attribute_rel : BA_REL STRING_VAL BU_SG_REL ID SG INT_VAL signal_name attribute_value ';' '''
        pass

    def p_attribute_definition_default_list(self, p):
        '''attribute_definition_default_list : empty
                                             | attribute_definition_default attribute_definition_default_list'''
        pass

    def p_attribute_definition_default(self, p):
        '''attribute_definition_default : attribute_definition_object_or_relation STRING_VAL INT_VAL ';'
                                        | attribute_definition_object_or_relation STRING_VAL DOUBLE_VAL ';'
                                        | attribute_definition_object_or_relation STRING_VAL STRING_VAL ';' '''
        pass

    def p_attribute_definition_object_or_relation(self, p):
        '''attribute_definition_object_or_relation : BA_DEF_DEF
                                                   | BA_DEF_DEF_REL'''
        pass

    def p_attribute_definition_list(self, p):
        '''attribute_definition_list : empty
                                     | attribute_definition attribute_definition_list'''
        pass

    def p_attribute_definition(self, p):
        '''attribute_definition : attribute_object_type STRING_VAL INT INT_VAL INT_VAL ';'
                                | attribute_object_type STRING_VAL FLOAT double_val double_val ';'
                                | attribute_object_type STRING_VAL STRING ';'
                                | attribute_object_type STRING_VAL ENUM comma_string_list ';'
                                | attribute_object_type STRING_VAL HEX INT_VAL INT_VAL ';' '''
        if p[2] == 'GenMsgSendType' and p[3] == 'ENUM':
            self.send_types = p[4]
            self.send_types.reverse()

    def p_attribute_object_type(self, p):
        '''attribute_object_type : BA_DEF
                                 | BA_DEF BU
                                 | BA_DEF BO
                                 | BA_DEF SG
                                 | BA_DEF EV
                                 | BA_DEF_REL BU_SG_REL
                                 | BA_DEF_REL BU_BO_REL'''
        if len(p) == 3:
            p[0] = p[2]

    def p_val_list(self, p):
        '''val_list : empty
                    | val val_list'''
        pass

    def p_val(self, p):
        '''val : VAL INT_VAL signal_name val_map ';'
               | VAL ID val_map ';' '''
        if len(p) == 6:
            self.signalDict[p[3].lower()].values = p[4]

    def p_val_map(self, p):
        '''val_map : empty
                   | val_map_entry val_map'''
        if p[1]:
            p[0] = p[2]
            p[2][p[1][1]] = p[1][0]
        else:
            p[0] = {}

    def p_val_map_entry(self, p):
        '''val_map_entry : INT_VAL STRING_VAL'''
        p[0] = (p[1], p[2].lower())

    def p_sig_valtype_list(self, p):
        '''sig_valtype_list : empty
                            | sig_valtype sig_valtype_list'''
        pass

    def p_sig_valtype(self, p):
        '''sig_valtype : SIG_VALTYPE INT_VAL ID ':' INT_VAL ';' '''
        pass

    def p_comment_list(self, p):
        '''comment_list : empty
                        | comment comment_list'''
        pass

    def p_comment(self, p):
        '''comment : CM STRING_VAL ';'
                   | CM EV ID STRING_VAL ';'
                   | CM BU ID STRING_VAL ';'
                   | CM BO INT_VAL STRING_VAL ';'
                   | CM SG INT_VAL ID STRING_VAL ';' '''
        pass

    def p_mux_info(self, p):
        '''mux_info : empty
                    | ID'''
        pass

    def p_signal_name(self, p):
        '''signal_name : ID'''
        p[0] = p[1]

    def p_signal_name_list(self, p):
        '''signal_name_list : space_identifier_list'''
        p[0] = p[1]

    def p_space_identifier_list(self, p):
        '''space_identifier_list : ID
                                 | ID space_identifier_list'''
        pass

    def p_comma_identifier_list(self, p):
        '''comma_identifier_list : ID
                                 | ID ',' comma_identifier_list'''
        pass

    def p_comma_string_list(self, p):
        '''comma_string_list : STRING_VAL
                             | STRING_VAL ',' comma_string_list'''
        if len(p) == 4:
            p[0] = p[3]
            p[0].append(p[1])
        else:
            p[0] = [p[1]]

    def p_double_val(self, p):
        '''double_val : DOUBLE_VAL
                      | NAN
                      | INT_VAL'''
        if 'NAN' != p[1]:
            p[0] = float(p[1])
        else:
            p[0] = None

    def p_bit_start(self, p):
        '''bit_start : INT_VAL'''
        p[0] = p[1]

    def p_bit_len(self, p):
        '''bit_len : INT_VAL'''
        p[0] = p[1]

    def p_scale(self, p):
        '''scale : double_val'''
        p[0] = p[1]

    def p_offset(self, p):
        '''offset : double_val'''
        p[0] = p[1]

    def p_min(self, p):
        '''min : double_val'''
        p[0] = p[1]

    def p_max(self, p):
        '''max : double_val'''
        p[0] = p[1]

    def p_endianness(self, p):
        '''endianness : INT_VAL'''
        p[0] = p[1]

    def p_signedness(self, p):
        '''signedness : '+'
                      | '-' '''
        pass

    def p_signal_group(self, p):
        '''signal_group : SIG_GROUP INT_VAL ID INT_VAL ':' signal_name_list ';' '''
        pass

    def p_signal_group_list(self, p):
        '''signal_group_list : empty
                             | signal_group signal_group_list'''
        pass

    def p_message_transmitters(self, p):
        '''message_transmitters : BO_TX_BU INT_VAL ':' comma_identifier_list ';' '''
        pass

    def p_message_transmitter_list(self, p):
        '''message_transmitter_list : empty
                                    | message_transmitters message_transmitter_list'''
        pass

    def p_empty(self, p):
        'empty :'
        pass


def _msbMap():
    """Return a translation dictionary for converting byte order."""
    msbMap = {}
    for x in range(9):
        if x > 1:
            littleEndian = 0
            bigEndian = (x-1)*8
            ret = {}
            for i in range(x/2*8):
                ret[bigEndian] = littleEndian
                ret[littleEndian] = bigEndian
                littleEndian += 1
                bigEndian += 1
                if bigEndian % 8 == 0:
                    bigEndian -= 16
            msbMap[x] = ret
    return msbMap


def importDBC(path):
    """Imports a vector database file"""

    with open(path, 'r') as inputfile:
        dbc = inputfile.read()

    # Construct lexer
    l = DBCLexer(debug=False)

    # Construct parser and parse file
    p = DBCParser(l, write_tables=0, debug=False)
    p.parse(dbc)
    msbMap = _msbMap()
    for msg in p.dbc.messages.values():
        setendianness = False
        if msg.send_type_num is not None and\
           msg.send_type_num < len(p.send_types):
            msg.send_type = p.send_types[msg.send_type_num]
        for sig in msg.signals:
            if not setendianness:
                if msg.period:
                    p.dbc.periodics.append(msg)
                if msg.id > 0xFFFF:
                    if msg.sender.lower() in p.dbc.nodes:
                        sender = p.dbc.nodes[msg.sender.lower()].sourceID
                        if (sender&0xF00) > 0:
                            print(msg.name)
                        msg.id = (msg.id&0xFFFF000)|0x10000000|sender
                    else:
                        print(msg.sender, msg.name)
                msg.endianness = sig.endianness
                setendianness = True
            if msg.dlc > 0:
                try:
                    sig.bit_start = msbMap[msg.dlc][sig.bit_msb] - (sig.bit_len-1)
                except KeyError: # This only happens when the msb doesn't change
                    sig.bit_start = sig.bit_msb-(sig.bit_len-1)
                sig.set_mask()
                if sig.initVal is not None:
                    sig.set_val(sig.initVal * sig.scale + sig.offset)
    return p


def main():
    """."""
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    fspec = sys.argv[1]

    # Read whole DBC file
    with open(fspec, 'r') as inputfile:
        dbc = inputfile.read()

    # Construct lexer
    l = DBCLexer(debug=False)

    # Construct parser and parse file
    p = DBCParser(l, write_tables=0, debug=False)
    p.parse(dbc)

    nodes = []
    messages = []
    signals = []
    for node in p.dbc.nodes.values():
        nodes.append(node)
        for msg in node.txMessages:
            messages.append(msg)
            for sig in msg.signals:
                signals.append(sig)
    print('----------------------------------------------------')
    print('Import Statistics')
    print('----------------------------------------------------')
    print('Nodes: '+str(len(nodes)))
    print('Messages: '+str(len(messages)))
    print('Signals: '+str(len(signals)))
    print('----------------------------------------------------')
    print('Test Structure - All signals of a message in a node\n')

    if len(nodes) > 0:
        print('N - '+nodes[0].name)
        print('   M - '+msg.name)
        if len(nodes[0].txMessages) > 0:
            for sig in nodes[0].txMessages[0].signals:
                print('      S - '+sig.name)

if __name__ == '__main__':
    main()
