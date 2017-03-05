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
import ply.lex as lex
import ply.yacc as yacc

class DBCFile(object):
    """DBC file object"""
    def __init__(self):
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
    """DBC node object"""
    def __init__(self, name):
        self.name = name
        self.sourceID = 0
        self.ecuID = 0
        self.txMessages = []
        self.rxMessages = []

class DBCMessage(object):
    """DBC message object"""
    def __init__(self, msgid, name, length, sender, signals, comment,
                 attributes, transmitters):
        self.id = int(msgid)
        self.txId = int(msgid)
        self.dlc = length
        self.data = 0
        self.initData = 0
        self.endianess = 0
        self.name = str(name)
        self.sender = str(sender)
        self.signals = signals
        self.comment = str(comment)
        self.attributes = attributes
        self.transmitters = transmitters
        self.cycleTime = 0
        self.sending = False

    def __str__(self):
        return "{id:0x%03x name:%s, length:%d, sender:%s, comment:%s}" % (
            self.id, self.name, self.length, self.sender, self.comment)

class DBCSignal(object):
    """DBC signal object"""
    def __init__(self, name, mux, bit_msb, bit_len, endianess, signedness,
                 scale, offset, min_val, max_val, units, receivers):
        self.name = name
        self.mux = mux
        self.bit_msb = bit_msb
        self.bit_len = bit_len
        self.endianess = endianess
        self.signedness = signedness
        self.scale = scale
        self.offset = offset
        self.min_val = min_val
        self.max_val = max_val
        self.units = units
        self.receivers = receivers
        self.fullName = ''
        self.values = {}
        self.msgID = 0
        self.val = 0
        self.initVal = 0
        self.sendOnInit = 0
        self.mask = 0
        self.bit_start = 0

    def setVal(self, num, force=False):
        """Sets the signal's value based on the offset and scale defined in
           the dbc file"""
        negative = False
        num = int((float(num)-float(self.offset))/float(self.scale))
        if num < 0:
            num = abs(num)
            negative = True

        size = len(bin(num)[2:])
        if not force:
            if size > self.bit_len:
                return False
        else:
            logging.warning('Ignoring dbc specs for this signal value')

        if negative:
            num = self._twosComplement(num)

        self.val = num<<self.bit_start
        return True

    def getVal(self):
        """Gets the signal's value operating exactly opposite of setVal"""
        tmp = self.val>>self.bit_start
        currVal = (tmp*self.scale+self.offset)
        # Check if currVal is really supposed to be negative
        if currVal > 0 and self.min_val < 0:
            bval = '{:b}'.format(int(currVal))
            if bval[0] == '1' and len(bval) == self.bit_len:
                currVal = float(-self._twosComplement(int(currVal)))
        if self.values.keys():
            for key, val in self.values.items():
                if val == currVal:
                    return key
        else:
            return currVal

    def _twosComplement(self, num):
        """ Returns the twos complement value of a number """
        tmp = bin(num)[2:]
        tmp = tmp.replace('0', '2')
        tmp = tmp.replace('1', '0')
        tmp = tmp.replace('2', '1')

        while len(tmp) < self.bit_len:
            tmp = '1'+tmp
        return int(tmp, 2)+1

    def setMask(self):
        """Sets the signals mask which is used to set the change the signal
           value within the message data"""
        if self.bit_start < 0:
            print self.name
        self.mask = pow(2, self.bit_len)-1 << self.bit_start

class DBCEnvVar(object):
    """DBC environmental variable object"""
    def __init__(self, name, etype, minV, maxV, unit, initial, index, access,
                 nodes=None, vals=None, comment=""):
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
            print repr(tok.type), repr(tok.value)

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
        t.lexer.lineno += t.value.count("\n")

class DBCParser(object):
    """The main DBC parser object"""
    def __init__(self, lexer=None, **kwargs):
        self.dbc = DBCFile()
        self.signalDict = {}
        self.signalDictByName = {}
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
        print "Syntax error at token %s (%s) on line %d" % (p.type, p.value,
                                                            p.lineno)
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
        if len(p[3]) > 3:
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
            try:
                self.nodeDict[p[1].sender.lower()].txMessages.append(p[1])
            except KeyError:
                print 'Error in dbc - Node: ' + str(p[1].sender.lower())+' - is invalid!'
            self.msgDict = p[0]
        else:
            p[0] = {}

    def p_message(self, p):
        '''message : BO INT_VAL ID ':' INT_VAL ID signal_list'''
        p[0] = DBCMessage(p[2], p[3], p[5], p[6], p[7], "", None, None)
        for sig in p[7]:
            sig.msgID = p[2]

    def p_signal_list(self, p):
        '''signal_list : empty
                       | signal signal_list'''
        if p[1]:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = []
        pass

    def p_signal(self, p):
        '''signal : SG signal_name mux_info ':' bit_start '|' bit_len '@' endianess signedness '(' scale ',' offset ')' '[' min '|' max ']' STRING_VAL comma_identifier_list'''
        p[0] = DBCSignal(p[2], p[3], p[5], p[7], p[9], p[10], p[12], p[14], p[17], p[19],
                        p[21], p[22])
        self.signalDict[p[2].lower()] = p[0]
        pass

    # Environment variables
    #########################################################################

    ###
    def p_envvar_list(self, p):
        '''envvar_list : empty
                       | envvar envvar_list'''
        if p[1]:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = []


    ###
    def p_envvar(self, p):
        '''envvar : EV ID ':' INT_VAL '[' double_val '|' double_val ']' \
                    STRING_VAL double_val INT_VAL DUMMY_NODE_VECTOR comma_identifier_list ';' '''
        p[0] = DBCEnvVar(p[2], p[4], p[6], p[8], p[10], p[11], p[12], p[13], p[14])

    ###
    def p_envvar_data_list(self, p):
        '''envvar_data_list : empty
                            | envvar_data envvar_data_list'''
        pass

    ###
    def p_envvar_data(self, p):
        '''envvar_data : ENVVAR_DATA ID ':' INT_VAL ';' '''
        pass

    def p_attribute_value(self, p):
        '''attribute_value : INT_VAL
                           | STRING_VAL
                           | DOUBLE_VAL'''
        p[0] = p[1]
        pass


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
            self.msgDict[p[4]].cycleTime = p[5]
        pass

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

    # set context dependent attribute value type
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
        pass

    def p_attribute_object_type(self, p):
        '''attribute_object_type : BA_DEF
                                 | BA_DEF BU
                                 | BA_DEF BO
                                 | BA_DEF SG
                                 | BA_DEF EV
                                 | BA_DEF_REL BU_SG_REL
                                 | BA_DEF_REL BU_BO_REL'''
        pass

    #*********************************************************************

    def p_val_list(self, p):
        '''val_list : empty
                    | val val_list'''
        pass

    def p_val(self, p):
        '''val : VAL INT_VAL signal_name val_map ';'
               | VAL ID val_map ';' '''
        if len(p) == 6:
            self.signalDict[p[3].lower()].values = p[4]
        pass

    def p_val_map(self, p):
        '''val_map : empty
                   | val_map_entry val_map'''
        if p[1]:
            p[0] = p[2]
            p[2][p[1][1]] = p[1][0]
        else:
            p[0] = {}
        pass

    def p_val_map_entry(self, p):
        '''val_map_entry : INT_VAL STRING_VAL'''
        p[0] = (p[1], p[2].lower())
        pass

    #*********************************************************************

    def p_sig_valtype_list(self, p):
        '''sig_valtype_list : empty
                            | sig_valtype sig_valtype_list'''
        pass

    # set signal value type in target signal
    #
    # SIG_VALTYPE:
    # no section - signed or unsigned
    # 1 - IEEE float
    # 2 - IEEE double
    #
    def p_sig_valtype(self, p):
        '''sig_valtype : SIG_VALTYPE INT_VAL ID ':' INT_VAL ';' '''
        pass

    #*********************************************************************

    def p_comment_list(self, p):
        '''comment_list : empty
                        | comment comment_list'''
        pass

    # TODO: append comment to object
    def p_comment(self, p):
        '''comment : CM STRING_VAL ';'
                   | CM EV ID STRING_VAL ';'
                   | CM BU ID STRING_VAL ';'
                   | CM BO INT_VAL STRING_VAL ';'
                   | CM SG INT_VAL ID STRING_VAL ';' '''
        pass

    #*********************************************************************

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
        pass

    # double_val or int_val as float
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

    def p_endianess(self, p):
        '''endianess : INT_VAL'''
        p[0] = p[1]

    def p_signedness(self, p):
        '''signedness : '+'
                      | '-' '''
        pass

    # signal group
    def p_signal_group(self, p):
        '''signal_group : SIG_GROUP INT_VAL ID INT_VAL ':' signal_name_list ';' '''
        pass

    # signal group_list
    def p_signal_group_list(self, p):
        '''signal_group_list : empty
                             | signal_group signal_group_list'''
        pass

    # TODO: use comma_node_dict
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
    """Creates a translation dictionary for converting byte order"""
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
        setEndianess = False
        for sig in msg.signals:
            if not setEndianess:
                if msg.cycleTime != 0:
                    p.dbc.periodics.append(msg)
                if msg.id > 0xFFFF:
                    if p.dbc.nodes.has_key(msg.sender.lower()):
                        sender = p.dbc.nodes[msg.sender.lower()].sourceID
                        if (sender&0xF00) > 0:
                            print msg.name
                        msg.txId = (msg.id&0xFFFF000)|0x10000000|sender
                    else:
                        print msg.sender, msg.name
                msg.endianess = sig.endianess
                setEndianess = True
            if msg.dlc > 0:
                try:
                    sig.bit_start = msbMap[msg.dlc][sig.bit_msb] - (sig.bit_len-1)
                except KeyError: # This only happens when the msb doesn't change
                    sig.bit_start = sig.bit_msb-(sig.bit_len-1)
                sig.setMask()
                sig.setVal(sig.initVal)
                msg.data = msg.data|abs(sig.val)
                msg.initData = msg.data

    return p

def main():
    """The main program"""
    if len(sys.argv) != 2:
        print __doc__
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
    print '----------------------------------------------------'
    print 'Import Statistics'
    print '----------------------------------------------------'
    print 'Nodes: '+str(len(nodes))
    print 'Messages: '+str(len(messages))
    print 'Signals: '+str(len(signals))
    print '----------------------------------------------------'
    print 'Test Structure - All signals of a message in a node\n'

    if len(nodes) > 0:
        print 'N - '+nodes[0].name
        print '   M - '+msg.name
        if len(nodes[0].txMessages) > 0:
            for sig in nodes[0].txMessages[0].signals:
                print '      S - '+sig.name

if __name__ == '__main__':
    main()
