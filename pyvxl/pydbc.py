#!/usr/bin/env python

"""DBC file parser.

Based on the DBC file parser part of
http://sourceforge.net/projects/cantools/ .

Usage:

    pydbc.py <DBC file specification>

Regerences:
    http://www.dabeaz.com/ply/ply.html
    http://www.dabeaz.com/ply/PLYTalk.pdf
"""

from ply.lex import lex
from ply.yacc import yacc


class DBCEnvVar:
    """DBC environmental variable object."""

    def __init__(self, name, etype, minV, maxV, unit, initial, index,  # noqa
                 access, nodes=None, vals=None, comment=""):  # noqa
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

    def __str__(self):  # noqa
        return (f'{{name:{self.name}, type:{self.type}, min:{self.min}, '
                f'max:{self.max}, unit:{self.unit}, initial:{self.initial}, '
                f'index:{self.index}, access:{self.access}, '
                f'comment:{self.comment}}}')


class DBCLexer:
    """A lex based DBC lexical analyzer."""

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
        'VERSION': 'VERSION',
        'BO_': 'BO',               # Botschaft (message)
        'BS_': 'BS',
        'BU_': 'BU',               # Steuergeraet (controller)
        'SG_': 'SG',               # Signal
        'EV_': 'EV',               # Environment
        'SIG_VALTYPE_': 'SIG_VALTYPE',
        'NS_': 'NS',
        'INT': 'INT',
        'FLOAT': 'FLOAT',
        'NAN': 'NAN',
        'STRING': 'STRING',
        'ENUM': 'ENUM',
        'HEX': 'HEX',
        'NS_DESC_': 'NS_DESC',
        'CM_': 'CM',                   # Comment
        'BA_DEF_': 'BA_DEF',               # Attribut-Definition
        'BA_': 'BA',                   # Attribut
        'VAL_': 'VAL',
        'CAT_DEF_': 'CAT_DEF',
        'CAT_': 'CAT',
        'FILTER': 'FILTER',
        'BA_DEF_DEF_': 'BA_DEF_DEF',
        'EV_DATA_': 'EV_DATA',
        'ENVVAR_DATA_': 'ENVVAR_DATA',
        'SGTYPE_': 'SGTYPE',
        'SGTYPE_VAL_': 'SGTYPE_VAL',
        'BA_DEF_SGTYPE_': 'BA_DEF_SGTYPE',
        'BA_SGTYPE_': 'BA_SGTYPE',
        'SIG_TYPE_REF_': 'SIG_TYPE_REF',
        'VAL_TABLE_': 'VAL_TABLE',
        'SIG_GROUP_': 'SIG_GROUP',
        'SIGTYPE_VALTYPE_': 'SIGTYPE_VALTYPE',
        'BO_TX_BU_': 'BO_TX_BU',
        'BA_DEF_REL_': 'BA_DEF_REL',
        'BA_REL_': 'BA_REL',
        'BA_DEF_DEF_REL_': 'BA_DEF_DEF_REL',
        'BU_SG_REL_': 'BU_SG_REL',
        'BU_EV_REL_': 'BU_EV_REL',
        'BU_BO_REL_': 'BU_BO_REL',
        'SG_MUL_VAL_': 'SG_MUL_VAL',
    }

    # Ignored characters
    t_ignore = " \t\r"

    # Literal characters
    literals = ":;|,@+-[]()"

    # Lexer constructor
    def __init__(self, **kwargs):  # noqa
        self.lexer = lex(module=self, **kwargs)

    # Lexing error
    def t_error(self, t):  # noqa
        print("Illegal character '%s' on line %d" % (t.value[0],
                                                     t.lexer.lineno))
        t.lexer.skip(1)

    # Dummy node vector
    def t_dummy_node_vector(self, t):  # noqa
        r'DUMMY_NODE_VECTOR[0-9]+'
        t.value = int(t.value[17:])
        t.type = 'DUMMY_NODE_VECTOR'
        return t

    # Identifier
    def t_id(self, t):  # noqa
        r'[a-zA-Z_][_a-zA-Z0-9]*'
        # Check for reserved identifiers
        t.type = self.reserved.get(t.value, 'ID')
        return t

    # String literal
    def t_string(self, t):  # noqa
        r'\"([^"\\]|(\\.))*\"'
        if len(t.value) > 2:
            t.value = t.value[1:-1]
        else:
            t.value = ""
        t.type = 'STRING_VAL'
        return t

    # (Double precision) floating point number literal
    def t_double_val(self, t):  # noqa
        r'[-+]?[0-9]+((\.[0-9]+([eE][-+]?[0-9]+)?)|([eE][-+]?[0-9]+))'
        t.value = float(t.value)
        t.type = 'DOUBLE_VAL'
        return t

    # Decimal integer number literal
    def t_decnumber(self, t):  # noqa
        r'[-+]?[0-9]+'
        t.value = int(t.value)
        t.type = 'INT_VAL'
        return t

    # Hexadecimal integer number literal
    def t_hexnumber(self, t):  # noqa
        r'0x[0-9a-fA-F]+'
        t.value = int(t.value, 16)
        t.type = 'INT_VAL'
        return t

    # New-line detection
    def t_newline(self, t):  # noqa
        r'\n+'
        t.lexer.lineno += t.value.count('\n')


class DBCParser:
    """A yacc based DBC parser."""

    def __init__(self, path, node_type, message_type, signal_type, **kwargs):  # noqa
        self.path = path
        self.node_type = node_type
        self.message_type = message_type
        self.signal_type = signal_type
        self.can_fd_support = False
        self.nodes = {}
        self.messages = {}
        self.signals = {}
        self.lexer = DBCLexer(debug=False)
        self.tokens = self.lexer.tokens
        self.parser = yacc(module=self, **kwargs)
        with open(path, 'r') as f:
            dbc = f.read()
        self.parser.parse(dbc, self.lexer.lexer, 0, 0, None)

    def p_error(self, p):
        """Print a parsing error."""
        print(f'\nSyntax error while importing {self.path} at token {p.type} '
              f'({p.value}) on line {p.lineno}\n')

    def p_dbc(self, p):  # noqa
        """dbc : version \
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
                 signal_group_list"""
        pass

    def p_version(self, p):  # noqa
        """version : VERSION STRING_VAL"""
        p[0] = p[2]

    def p_symbol_section(self, p):  # noqa
        """symbol_section : NS ':'
                          | NS ':' symbol_list"""
        if len(p) > 3 and len(p[3]) > 3:
            p[0] = p[3]
        else:
            p[0] = []

    def p_symbol_list(self, p):  # noqa
        """symbol_list : symbol
                       | symbol symbol_list"""
        if len(p) > 2:
            p[0] = p[2]
            p[0].insert(0, p[1])
        else:
            p[0] = [p[1]]

    def p_symbol(self, p):  # noqa
        """symbol : NS_DESC
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
                  | SG_MUL_VAL"""
        p[0] = p[1]

    def p_message_section(self, p):  # noqa
        """message_section : BS ':' """
        pass

    def p_space_node_dict(self, p):  # noqa
        """space_node_dict : empty
                           | ID space_node_dict"""
        if p[1]:
            p[0] = p[2]
            p[0][p[1].lower()] = self.node_type(p[1])
        else:
            p[0] = self.nodes

    def p_node_dict(self, p):  # noqa
        """node_dict : BU ':' space_node_dict"""
        p[0] = p[3]

    def p_valtable_list(self, p):  # noqa
        """valtable_list : empty
                         | valtable valtable_list"""
        pass

    def p_valtable(self, p):  # noqa
        """valtable : VAL_TABLE ID val_map ';' """
        pass

    def p_message_dict(self, p):  # noqa
        """message_dict : empty
                        | message message_dict"""
        if p[1]:
            p[0] = p[2]
            p[0][p[1].id] = p[1]
            if p[1].sender.lower() not in self.nodes:
                self.nodes[p[1].sender.lower()] = self.node_type(p[1].sender)
            self.nodes[p[1].sender.lower()].tx_messages.append(p[1])
        else:
            p[0] = self.messages

    def p_message(self, p):  # noqa
        """message : BO INT_VAL ID ':' INT_VAL ID signal_list"""
        p[0] = self.message_type(p[2], p[3], p[5], p[6], p[7])
        for sig in p[7]:
            sig.msg_id = p[2]

    def p_signal_list(self, p):  # noqa
        """signal_list : empty
                       | signal signal_list"""
        if p[1]:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = []

    def p_signal(self, p):  # noqa
        """signal : SG signal_name mux_info ':' bit_msb '|' bit_len '@' endianness signedness '(' scale ',' offset ')' '[' min '|' max ']' STRING_VAL comma_identifier_list"""
        p[0] = self.signal_type(p[2], p[3], p[5], p[7], p[9], p[10], p[12],
                                p[14], p[17], p[19], p[21], p[22])
        if p[2].lower() in self.signals:
            self.signals[p[2].lower()].append(p[0])
        else:
            self.signals[p[2].lower()] = [p[0]]

    def p_envvar_list(self, p):  # noqa
        """envvar_list : empty
                       | envvar envvar_list"""
        if p[1]:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = []

    def p_envvar(self, p):  # noqa
        """envvar : EV ID ':' INT_VAL '[' double_val '|' double_val ']' \
                    STRING_VAL double_val INT_VAL DUMMY_NODE_VECTOR comma_identifier_list ';' """
        p[0] = DBCEnvVar(p[2], p[4], p[6], p[8], p[10], p[11], p[12], p[13], p[14])

    def p_envvar_data_list(self, p):  # noqa
        """envvar_data_list : empty
                            | envvar_data envvar_data_list"""
        if p[1]:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = []

    def p_envvar_data(self, p):  # noqa
        """envvar_data : ENVVAR_DATA ID ':' INT_VAL ';' """
        pass

    def p_attribute_value(self, p):  # noqa
        """attribute_value : INT_VAL
                           | STRING_VAL
                           | DOUBLE_VAL"""
        p[0] = p[1]

    def p_attribute_list(self, p):  # noqa
        """attribute_list : empty
                          | attribute attribute_list"""
        if p[1]:
            p[0] = p[2]
            p[0][p[1][0]] = p[1][1]
        else:
            p[0] = {}

    def p_attribute(self, p):  # noqa
        """attribute : BA STRING_VAL attribute_value ';'
                     | BA STRING_VAL BU ID attribute_value ';'
                     | BA STRING_VAL BO INT_VAL attribute_value ';'
                     | BA STRING_VAL SG INT_VAL ID attribute_value ';'
                     | BA STRING_VAL EV ID attribute_value ';' """
        if p[2] == 'SignalLongName':
            for sig in self.messages[int(p[4]) & 0x1FFFFFFF].signals:
                if sig.name == p[5]:
                    sig.long_name = p[6]
        elif p[2] == 'GenSigStartValue':
            for sig in self.messages[int(p[4]) & 0x1FFFFFFF].signals:
                if sig.name == p[5]:
                    sig.init_val = p[6]
                    try:
                        sig.val = sig.init_val
                    except Exception:
                        pass
        elif p[2] == 'GenSigSendOnInit':
            for sig in self.messages[int(p[4]) & 0x1FFFFFFF].signals:
                if sig.name == p[5]:
                    sig.send_on_init = p[6]
        elif p[2] == 'source_id':
            self.nodes[p[4].lower()].source_id = p[5]
        elif p[2] == 'SystemMessageLongSymbol':
            self.messages[int(p[4]) & 0x1FFFFFFF].long_name = p[5]
        elif p[2] == 'GenMsgCycleTime':
            self.messages[int(p[4]) & 0x1FFFFFFF].period = p[5]
        elif p[2] == 'GenMsgDelayTime':
            self.messages[int(p[4]) & 0x1FFFFFFF].delay = p[5]
        elif p[2] == 'GenMsgSendType':
            # This was removed since I can't find a standard specifying these
            # send types and how they should be implemented. I've also seen
            # DBCs from different OEMs with different names used so I think
            # there might not be a standard.
            pass
        elif p[2] == 'GenMsgNrOfRepetitions':
            self.messages[int(p[4]) & 0x1FFFFFFF].repetitions = p[5]
        elif p[2] == 'VFrameFormat':
            self.messages[int(p[4]) & 0x1FFFFFFF].id_format = p[5]
        elif p[2] == 'CANFD_BRS':
            self.messages[int(p[4]) & 0x1FFFFFFF].brs = bool(p[5])

    def p_attribute_rel_list(self, p):  # noqa
        """attribute_rel_list : empty
                              | attribute_rel attribute_rel_list"""
        pass

    def p_attribute_rel(self, p):  # noqa
        """attribute_rel : BA_REL STRING_VAL BU_SG_REL ID SG INT_VAL signal_name attribute_value ';' """
        pass

    def p_attribute_definition_default_list(self, p):  # noqa
        """attribute_definition_default_list : empty
                                             | attribute_definition_default attribute_definition_default_list"""
        pass

    def p_attribute_definition_default(self, p):  # noqa
        """attribute_definition_default : attribute_definition_object_or_relation STRING_VAL INT_VAL ';'
                                        | attribute_definition_object_or_relation STRING_VAL DOUBLE_VAL ';'
                                        | attribute_definition_object_or_relation STRING_VAL STRING_VAL ';' """
        pass

    def p_attribute_definition_object_or_relation(self, p):  # noqa
        """attribute_definition_object_or_relation : BA_DEF_DEF
                                                   | BA_DEF_DEF_REL"""
        pass

    def p_attribute_definition_list(self, p):  # noqa
        """attribute_definition_list : empty
                                     | attribute_definition attribute_definition_list"""
        pass

    def p_attribute_definition(self, p):  # noqa
        """attribute_definition : attribute_object_type STRING_VAL INT INT_VAL INT_VAL ';'
                                | attribute_object_type STRING_VAL FLOAT double_val double_val ';'
                                | attribute_object_type STRING_VAL STRING ';'
                                | attribute_object_type STRING_VAL ENUM comma_string_list ';'
                                | attribute_object_type STRING_VAL HEX INT_VAL INT_VAL ';' """
        if p[2] == 'GenMsgSendType' and p[3] == 'ENUM':
            # This was removed since I can't find a standard specifying these
            # send types and how they should be implemented. I've also seen
            # DBCs from different OEMs with different names used so I think
            # there might not be a standard.
            pass
        elif p[2] == 'VFrameFormat' and p[3] == 'ENUM':
            self.can_fd_support = True

    def p_attribute_object_type(self, p):  # noqa
        """attribute_object_type : BA_DEF
                                 | BA_DEF BU
                                 | BA_DEF BO
                                 | BA_DEF SG
                                 | BA_DEF EV
                                 | BA_DEF_REL BU_SG_REL
                                 | BA_DEF_REL BU_BO_REL"""
        if len(p) == 3:
            p[0] = p[2]

    def p_val_list(self, p):  # noqa
        """val_list : empty
                    | val val_list"""
        pass

    def p_val(self, p):  # noqa
        """val : VAL INT_VAL signal_name val_map ';'
               | VAL ID val_map ';' """
        if len(p) == 6:
            for sig in self.messages[int(p[2]) & 0x1FFFFFFF].signals:
                if sig.name == p[3]:
                    sig.values = p[4]

    def p_val_map(self, p):  # noqa
        """val_map : empty
                   | val_map_entry val_map"""
        if p[1]:
            p[0] = p[2]
            p[2][p[1][1]] = p[1][0]
        else:
            p[0] = {}

    def p_val_map_entry(self, p):  # noqa
        """val_map_entry : INT_VAL STRING_VAL"""
        p[0] = (p[1], p[2])

    def p_sig_valtype_list(self, p):  # noqa
        """sig_valtype_list : empty
                            | sig_valtype sig_valtype_list"""
        pass

    def p_sig_valtype(self, p):  # noqa
        """sig_valtype : SIG_VALTYPE INT_VAL ID ':' INT_VAL ';' """
        pass

    def p_comment_list(self, p):  # noqa
        """comment_list : empty
                        | comment comment_list"""
        pass

    def p_comment(self, p):  # noqa
        """comment : CM STRING_VAL ';'
                   | CM EV ID STRING_VAL ';'
                   | CM BU ID STRING_VAL ';'
                   | CM BO INT_VAL STRING_VAL ';'
                   | CM SG INT_VAL ID STRING_VAL ';' """
        pass

    def p_mux_info(self, p):  # noqa
        """mux_info : empty
                    | ID"""
        pass

    def p_signal_name(self, p):  # noqa
        """signal_name : ID"""
        p[0] = p[1]

    def p_signal_name_list(self, p):  # noqa
        """signal_name_list : space_identifier_list"""
        p[0] = p[1]

    def p_space_identifier_list(self, p):  # noqa
        """space_identifier_list : ID
                                 | ID space_identifier_list"""
        if len(p) == 3:
            p[0] = p[2]
            p[0].append(p[1])
        else:
            p[0] = [p[1]]

    def p_comma_identifier_list(self, p):  # noqa
        """comma_identifier_list : ID
                                 | ID ',' comma_identifier_list"""
        if len(p) == 4:
            p[0] = p[3]
            p[0].append(p[1])
        else:
            p[0] = [p[1]]

    def p_comma_string_list(self, p):  # noqa
        """comma_string_list : STRING_VAL
                             | STRING_VAL ',' comma_string_list"""
        if len(p) == 4:
            p[0] = p[3]
            p[0].append(p[1])
        else:
            p[0] = [p[1]]

    def p_double_val(self, p):  # noqa
        """double_val : DOUBLE_VAL
                      | NAN
                      | INT_VAL"""
        if 'NAN' != p[1]:
            p[0] = p[1]
        else:
            p[0] = None

    def p_bit_msb(self, p):  # noqa
        """bit_msb : INT_VAL"""
        p[0] = p[1]

    def p_bit_len(self, p):  # noqa
        """bit_len : INT_VAL"""
        p[0] = p[1]

    def p_scale(self, p):  # noqa
        """scale : double_val"""
        p[0] = p[1]

    def p_offset(self, p):  # noqa
        """offset : double_val"""
        p[0] = p[1]

    def p_min(self, p):  # noqa
        """min : double_val"""
        p[0] = p[1]

    def p_max(self, p):  # noqa
        """max : double_val"""
        p[0] = p[1]

    def p_endianness(self, p):  # noqa
        """endianness : INT_VAL"""
        p[0] = p[1]

    def p_signedness(self, p):  # noqa
        """signedness : '+'
                      | '-' """
        pass

    def p_signal_group(self, p):  # noqa
        """signal_group : SIG_GROUP INT_VAL ID INT_VAL ':' signal_name_list ';' """
        pass

    def p_signal_group_list(self, p):  # noqa
        """signal_group_list : empty
                             | signal_group signal_group_list"""
        pass

    def p_message_transmitters(self, p):  # noqa
        """message_transmitters : BO_TX_BU INT_VAL ':' comma_identifier_list ';' """
        pass

    def p_message_transmitter_list(self, p):  # noqa
        """message_transmitter_list : empty
                                    | message_transmitters message_transmitter_list"""
        pass

    def p_empty(self, p):  # noqa
        'empty :'
        pass


def verify_signals(signals):
    """Verify signals can be set to their named, min and max values."""
    sig_count = 0
    errors = {'values_name_e': [], 'values_name': [],
              'values_num_e': [], 'values_num': [],
              'min_val_e': [], 'min_val': [],
              'max_val_e': [], 'max_val': []}
    for sig_list in signals.values():
        for sig in sig_list:
            sig_count += 1
            for name, val in sig.values.items():
                try:
                    sig.val = name
                except Exception as e:
                    errors['values_name_e'].append((sig, e))
                else:
                    try:
                        if sig.val != name:
                            txt = f'{name} != {sig.val}'
                            errors['values_name'].append((sig, txt))
                        if sig.raw_val != val:
                            txt = f'{sig.raw_val} != enum val for {sig.val}'
                            errors['values_num'].append((sig, txt))
                    except Exception:
                        pass
                try:
                    sig.val = val
                except Exception as e:
                    errors['values_num_e'].append((sig, e))
                else:
                    try:
                        if sig.val != name:
                            txt = f'{name} != {sig.val}'
                            errors['values_num'].append((sig, txt))
                        if sig.raw_val != val:
                            txt = f'{sig.raw_val} != enum val for {sig.val}'
                            errors['values_num'].append((sig, txt))
                    except Exception:
                        pass
            try:
                sig.val = sig.min_val
            except Exception as e:
                errors['min_val_e'].append((sig, e))
            else:
                if sig.num_val != sig.min_val:
                    txt = f'{sig.min_val} != {sig.num_val}'
                    errors['min_val'].append((sig, txt))
            try:
                sig.val = sig.max_val
            except Exception as e:
                errors['max_val_e'].append((sig, e))
            else:
                if sig.num_val != sig.max_val:
                    txt = f'{sig.num_val} != {sig.max_val}'
                    errors['max_val'].append((sig, txt))
    print(f'Total Signals; {sig_count}\n')
    print('Errors Found:')
    for err_type, err_list in errors.items():
        spaces = ' ' * (15 - len(err_type))
        print(f'\t{err_type}{spaces}{len(err_list)}')
    return errors
