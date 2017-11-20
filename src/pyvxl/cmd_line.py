#!/usr/bin/env python

"""
The command line program run when typing 'can'
"""

import sys, logging, traceback, socket, select, os, subprocess
from argparse import ArgumentParser
from colorama import Fore, Style
import config, settings
from pyvxl import CAN
from initbus import initbus

__program__ = 'can'


def initialize_bus(can, node=None):
    """Called by the command 'init' and by default starts all periodics found
       in the database except those transmitted by the device under test.

       For a more specific initialization, see initbus.py located in this
       directory.
    """
    can.hvWakeUp()
    if node:
        can.start_periodics(node)
    else:
        # Calls initbus() within initbus.py - currently being used in to
        # send required periodics not found in the database and inital signal
        # values simulating a running vehicle.
        initbus(can)

def print_help():
    """Called by the command h or help"""
    # pylint: disable=C0301
    helpcolor = Fore.RED + Style.BRIGHT
    helprst = Fore.RESET+Style.RESET_ALL
    # TODO: Convert this to a list and print like it's being piped to less
    print helpcolor+'Valid commands:'
    print ''
    print ' - Bus Manipulation -----------------------------------------------------------'
    print '  restart'
    print '     - Reconnects to the CAN bus. Useful if the error light on the CAN case is'
    print '       red.'
    print ''
    print '  init [node]'
    print '     - Without a value for [node], calls initbus.py, sending all signals'
    print '       defined in that file. With [node], calls vector.start_periodics(node),'
    print '       starting all periodics in the database except those transmitted by'
    print '       [node].'
    print ''
    print '  send signal <-f> <signal> <value> '
    print '     - Send the msg containing <signal> with the signal value = <value>.'
    print '       <-f> can be specified to send a value not defined in the dbc file.'
    print '       e.g., send signal system power mode run'
    print '        or    ""    ""   syspwrmd          ""'
    print ''
    print '  send message <msgID> <data>'
    print '     - Send a complete message similar to the way it is displayed in CANoe.'
    print '       <msgID> can be the hexadecimal id or full name of the message. <data>'
    print '       is the message data to be sent. If the data given is shorter than'
    print '       specified by the dlc in the database, \'0\'s will be appended to the'
    print '       left of the entered message data to make it the correct length.'
    print '       e.g., send message 0x10242040 02'
    print '        or    ""    ""      10242040 02'
    print ''
    print '  send diag <txMsgID> <data> <rxMsgID>'
    print '     - Send a diagnostic message and wait for a response. <txMsgID> is the'
    print '       message id or name to transmit from. <data> is the data which will'
    print '       be sent with that message. <rxMsgId> is the id or name of the'
    print '       message to wait for a response from.'
    print ''
    print '  send lastfound <signal|message> <value> '
    print '     - Sends the last found signal or message with <value>.'
    print '       e.g., send lastfound message 02'
    print '        or    ""     ""     signal run'
    print ''
    print '  wait <time> <msgId> [value]'
    print '     - Waits for <time>(ms) for msgId with value to be received. \'*\' can be'
    print '       used as a dont care. Returns 1 if found, else 0.'
    print '       e.g., wait 1000 0x10242040'
    print '              ""   ""      ""     02'
    print '              ""   ""      ""     *2'
    print ''
    print '  kill <signal|msgID>'
    print '     - Stops sending a periodic message'
    print '       e.g., stop system power mode'
    print '             stop syspwrmd'
    print '             stop 0x10242040'
    print ''
    print '  killnode <node>'
    print '     - Stops all periodic messages sent from <node>'
    print ''
    print '  killall'
    print '     - Stops all periodic messages'
    print ''
    print ' - Database & Bus Information -------------------------------------------------'
    print ''
    print '  config'
    print '     - Print the current vector hardware configuration'
    print ''
    print '  find node <string>'
    print '     - Prints all nodes found with <string> in their name'
    print ''
    print '  find message <string>'
    print '     - Prints all messages found with <string> in their name'
    print ''
    print '  find signal <string>'
    print '     - Prints all signals found with <string> in their name'
    print ''
    print '  periodics [info]'
    print '     - Prints all periodic messages being sent. If \'info\' is present, signals'
    print '       of each periodic and their values are also printed.'
    print ''
    print '  periodics info <val>'
    print '     - Prints current periodics including signal values. <val> can be either a'
    print '       message id, part of a message name, or part of a signal name.'
    print ''
    print '  log <command> [file]'
    print '     - Controls logging to [file]. <command> can be either \'start\' or \'stop\'.'
    print '       If [filename] is not specified, a default name will be chosen.'
    print ''
    print ' - Other ----------------------------------------------------------------------'
    print '  exit | ctrl+c | q     - Exit the app'
    print '  h | help              - Display this message'+helprst

def main():
    """This script is intended to test and demonstrate the functionality
       of the vector.py CANcase interface"""
    # pylint: disable=R0912,R0914
    parser = ArgumentParser(prog=__program__, description='A license free '+
                            'interface to the CAN bus')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="enable verbose output")
    parser.add_argument('-c', '--channel', help='the CAN channel or port to'+
                        ' connect to')
    parser.add_argument('-e', '--example-script', action='store_true',
                        help='prints the location of an example script and '+
                        'also runs it')
    parser.add_argument('-nl', '--network-listen', action='store_true',
                        help='start the program in network mode. it will then '+
                        'begin listening for commands on a port related to the'+
                        ' can channel')
    parser.add_argument('-ns', '--network-send', metavar='cmd', type=str,
                        nargs='+', help='commands to send to a separate '+
                        'instance of the program running in network mode')
    args = parser.parse_args()
    if args.network_send:
        messages = args.network_send
        if not args.channel:
            channel = config.get(config.PORT_CAN_ENV)
            if not channel:
                parser.error('please specify a CAN channel')
            else:
                channel = int(channel)
        else:
            try:
                channel = int(args.channel)
            except ValueError:
                parser.error('please specify a valid CAN channel')
        HOST = 'localhost'
        PORT = 50000+(2*channel)
        sendSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sendSock.connect((HOST, PORT))
        except socket.error:
            logging.error('Unable to connect to can!\n\nCheck that a verion'+
                          ' is running in network mode and that the channel'+
                          ' specified\nis correct.')
            sys.exit(1)
        sendSock.sendall(' '.join(messages))
        if len(messages) > 2:
            if messages[1] == 'diag':
                print sendSock.recv(128)
        sendSock.close()
        sys.exit(0)
    elif args.example_script:
        script = 'example_script.py'
        path = os.path.dirname(os.path.realpath(__file__))+'\\'+script
        print 'Example script located at: \n'+path
        try:
            action = raw_input('\nRun example? (y/n): ')
        except KeyboardInterrupt:
            pass
        if action.lower() == 'y':
            if args.channel:
                subprocess.call(['python', path, '-c', args.channel])
            else:
                subprocess.call(['python', path])
        sys.exit(0)
    if args.verbose:
        logging.basicConfig(format=settings.VERBOSE_DEBUG_MESSAGE,
                            level=logging.DEBUG)
    else:
        logging.basicConfig(format=settings.DEFAULT_DEBUG_MESSAGE,
                            level=logging.INFO)
    dbcPath = config.get(config.DBC_PATH_1)
    baudRate = config.get(config.CAN_BAUD_RATE_1)
    channel = config.get(config.CAN_CHANNEL_1)
    if args.channel:
        channel = args.channel
    try:
        if not channel:
            channel = raw_input('Enter the CAN channel you\'d like to open: ')
        if channel:
            try:
                channel = int(channel)
            except ValueError:
                logging.error('Invalid channel - defaulting to channel 1')
                channel = 1
        else:
            logging.warning('Defaulting to channel 1')
            channel = 1
        if not baudRate:
            baudRate = raw_input('Enter the baudrate for that channel: ')
        if baudRate:
            try:
                baudRate = int(baudRate)
            except ValueError:
                logging.error('Invalid baudrate - defaulting to 500kbaud')
                baudRate = 500000
        else:
            logging.warning('Defaulting to 500kbaud')
            baudRate = 500000
        imported = False
        can = CAN(channel, dbcPath, baudRate)
        can.start()
        if dbcPath:
            imported = can.import_dbc()
        while not imported:
            toprint = 'Enter the path to a dbc file (press enter to skip): '
            dbcPath = raw_input(toprint)
            if dbcPath:
                can.dbc_path = dbcPath
                imported = can.import_dbc()
            else:
                toprint1 = 'Skipping dbc import - '
                toprint2 = toprint1+'most functions will not work!\n'
                logging.warning(toprint2)
                imported = True
    except KeyboardInterrupt:
        print 'Exiting...'
        sys.exit(0)
    if not can.initialized and not can.imported:
        print ''
        logging.error('Unable to start without a database or CANcase')
        sys.exit(0)
    elif not can.initialized:
        logging.info('Starting in database only mode')
    elif not can.imported:
        logging.info('Starting in CAN only mode')
    validCommands = ['send', 'kill', 'killall', 'find', 'killnode', 'log',
                     'periodics', 'config', 'h', 'waitfor', 'help', 'exit',
                     'q', 'init', 'restart']
    HOST = ''
    PORT = 50000+(2*channel)
    sock = None
    conn = None
    if args.network_listen:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((HOST, PORT))
        sock.listen(1)
    while 1:
        try:
            if not args.network_listen:
                o = raw_input('> ')
            else:
                waiting = True
                while waiting:
                    inputr, [], [] = select.select([sock], [], [], 3)
                    for s in inputr:
                        if s == sock:
                            waiting = False
                conn, addr = sock.accept() # pylint: disable=W0612
                o = conn.recv(128)
            if o:
                s = o.split()
                command = s[0]
                value = s[-1]
                if command in validCommands:
                    if command == 'restart':
                        can.stop()
                        can.start()
                    elif command == 'send': # send message
                        if len(s) == 1:
                            logging.error('Send requires more arguments!')
                        elif s[1] == 'message':
                            if len(s) < 5:
                                if len(s) == 3:
                                    # send a message without data
                                    can.send_message(s[2], '')
                                elif len(s) == 4:
                                    # send a message with data
                                    can.send_message(s[2], s[3])
                                else:
                                    logging.error('Too few arguments!')
                            else:
                                msg = 'Too many values!\nType \'h\' to see the '
                                logging.error(msg+'correct format')
                        elif s[1] == 'signal':
                            # send a message only changing the signal value
                            if can.imported:
                                sigStop = len(s)-1
                                testSig = ''
                                force = False
                                if '-f' in s[2:-1]:
                                    force = True
                                    s.remove('-f')
                                # pylint: disable=W0612,C0301
                                for x in range(len(s[2:-1])):
                                    testSig = ' '.join(s[2:sigStop]).lower()
                                    if can.parser.dbc.signals.has_key(testSig):
                                        val = ' '.join(s[sigStop:]).lower()
                                        if can.parser.dbc.signals[testSig].values.keys() and not force:
                                            if can.parser.dbc.signals[testSig].values.has_key(val):
                                                can.send_signal(testSig, val)
                                                break
                                        else:
                                            try:
                                                can.send_signal(testSig, val, force)
                                                break
                                            except ValueError:
                                                pass
                                    elif can.parser.dbc.signalsByName.has_key(testSig):
                                        val = ' '.join(s[sigStop:]).lower()
                                        if can.parser.dbc.signalsByName[testSig].values.keys() and not force:
                                            if can.parser.dbc.signalsByName[testSig].values.has_key(val):
                                                can.send_signal(testSig, val)
                                                break
                                        else:
                                            try:
                                                can.send_signal(testSig, val, force)
                                                break
                                            except ValueError:
                                                pass
                                    sigStop -= 1
                                    # pylint: enable=C0301
                                else:
                                    msg = 'Invalid signal name or value!'
                                    logging.error(msg)
                        elif s[1] == 'diag':
                            if len(s) == 6:
                                data = can.send_diag(s[2], s[3], s[4],
                                                     respData=s[5])
                            elif len(s) == 5:
                                data = can.send_diag(s[2], s[3], s[4])
                            elif len(s) == 4:
                                data = can.send_diag(s[2], '', s[3])
                            else:
                                logging.error('Invalid number of arguments!')
                            if args.network_listen:
                                if data != False:
                                    conn.sendall(data)
                                else:
                                    conn.sendall('')
                        elif s[1] == 'lastfound':
                            if len(s) > 3:
                                value = ' '.join(s[3:])
                                if s[2] == 'message':
                                    if can.lastFoundMessage:
                                        last = can.lastFoundMessage.txId
                                        can.send_message(last, value)
                                    else:
                                        mg = ('No messages found'+
                                              ' in the last search!')
                                        logging.error(mg)
                                elif s[2] == 'signal':
                                    if can.lastFoundSignal:
                                        last = can.lastFoundSignal.name
                                        can.send_signal(last, value)
                                    else:
                                        mg = ('No signals found'+
                                              ' in the last search!')
                                        logging.error(mg)
                                else:
                                    logging.error('Invalid lastfound type!')
                            else:
                                logging.error('lastfound requires a'+
                                              ' type and value!')
                        else:
                            logging.error('Invalid send type!')
                    elif command == 'kill': # stop
                        name = ' '.join(s[1:])
                        can.kill_periodic(name)
                    elif command == 'killnode':
                        can.kill_node(s[1])
                    elif command == 'killall': # stopall
                        can.kill_periodics()
                    elif command == 'find': # find
                        if s[1] == 'node':
                            if len(s) > 2:
                                can.find_node(s[2])
                            else:
                                can.find_node('')
                        elif s[1] == 'message':
                            msg = ' '.join(s[2:])
                            can.find_message(msg, display=True)
                        elif s[1] == 'signal':
                            signal = ' '.join(s[2:])
                            can.find_signal(signal, display=True)
                        else:
                            logging.error('Invalid find type!')
                    elif o in ['exit', 'q']: # exit or q
                        break
                    elif o in ['help', 'h']: # help or h
                        print_help()
                    elif command == 'config':
                        can.print_config()
                        print ('Connected to channel: '+str(can.channel.value)+
                                ' @ '+str(can.baud_rate)+'Bd!')
                    elif command == 'waitfor':
                        data = ''
                        if len(s) == 3:
                            data = can.wait_for(s[1], s[2], '')
                        elif len(s) == 4:
                            data = can.wait_for(s[1], s[2], s[3])
                        else:
                            logging.error('Invalid number of arguments!')
                        if  args.network_listen:
                            if data != False:
                                conn.sendall(data)
                            else:
                                conn.sendall('')
                    elif command == 'init':
                        if len(s) > 1:
                            initialize_bus(can, node=s[1])
                        else:
                            initialize_bus(can)
                    elif command == 'periodics':
                        if len(s) > 1:
                            if s[1] == 'info':
                                if len(s) > 2:
                                    inp = ' '.join(s[2:])
                                    print inp
                                    can.print_periodics(info=True,
                                                        searchFor=inp)
                                else:
                                    can.print_periodics(info=True)
                            else:
                                logging.error('Invalid periodics type!')
                        else:
                            can.print_periodics()
                    elif command == 'log':
                        if len(s) > 1:
                            if s[1] == 'start':
                                if len(s) > 2:
                                    can.log_traffic(s[2])
                                else:
                                    can.log_traffic('CAN-log')
                            elif s[1] == 'stop':
                                can.stop_logging()
                            else:
                                logging.error('Invalid log command!')
                        else:
                            logging.error('Invalid log command!')
                else:
                    print 'Invalid command - type \'h\' or \'help\' for options'
                if args.network_listen:
                    conn.close()
        except EOFError:
            pass
        except KeyboardInterrupt:
            if args.network_listen and conn:
                conn.close()
            break
        except Exception:
            if args.network_listen and conn:
                conn.close()
            print '-' * 60
            traceback.print_exc(file=sys.stdout)
            print '-' * 60
            break
    sys.stdout.flush()
    can.stop()

if __name__ == "__main__":
    main()
