#!/usr/bin/env python

"""
Demonstrates the usage of pyvxl.CAN
"""

import logging, sys, os, math
from argparse import ArgumentParser
import settings
import CAN, initbus

__program__ = 'can_example'

def main(): # pylint: disable=C0111
    # pylint: disable=W0105

    # Create a parser and parse any command line arguements
    parser = ArgumentParser(prog=__program__, description=__doc__)
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="enable verbose output")
    parser.add_argument('-c', '--channel', help='the CAN channel or port to'+
                        ' connect to')
    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.basicConfig(format=settings.VERBOSE_DEBUG_MESSAGE,
                            level=logging.DEBUG)
    else:
        logging.basicConfig(format=settings.DEFAULT_DEBUG_MESSAGE,
                            level=logging.INFO)

    # Grab the variables stored in the setup.cfg file
    '''
    channel = config.get(config.PORT_CAN_ENV)
    dbc_path = config.get(config.DBC_PATH_ENV)
    baud_rate = config.get(config.CAN_BAUD_RATE_ENV)
    '''
    # To make this a working example, i've hardcoded values with a dbc file
    if args.channel:
        channel = int(args.channel)
    else:
        channel = 1
    dbc = 'a.dbc'
    dbc_path = os.path.dirname(os.path.realpath(__file__))+'\\'+dbc
    baud_rate = 33333
    if channel and dbc_path and baud_rate:
        can = CAN(channel, dbc_path, baud_rate)
        can.open_driver()
        can.set_channel(math.pow(2, can.drvConfig.channelCount-1))
        # Connect to the vector driver, hide the printed message
        if not can.start(display=False):
            sys.exit(1)
        # Import the database
        can.import_dbc()
    else:
        logging.error('Unable to find suitable environment variables!')
        sys.exit(1)


    """
    ----------------------A quick note about CAN messages----------------------
    All messages defined in the dbc file have an associated cycle time. If that
    cycle time equals 0, the message is considered non periodic. Vector will
    send a messages according to their cycle time. Periodic messages will be
    sent periodically and non periodic messages will be sent only once.
    ---------------------------------------------------------------------------
    """

    # Begin logging
    can.log_traffic('CAN-log')

    """send_signal - modify a single signal value"""
    # by full name - neither name nor value are case sensitive
    logging.info('='*60)
    logging.info('Sending signals')
    logging.info('-'*60)
    can.send_signal('system power mode', 'run')
    # by short name
    can.send_signal('syspwrmd', 'run')
    # signal with a numeric values
    can.send_signal('vehicle speed average driven', 80)
    # signal value forced to a number - useful when sending values not in the
    # dbc is required
    # TODO: implement this functionality
    #can.send_signal('system power mode', 2, force=True)

    """send_message - modify or begin sending an entire message"""
    logging.info('='*60)
    logging.info('Sending messages')
    logging.info('-'*60)
    # by by name
    can.send_message('engine_information_1_ls', 'f002')
    # by hex value
    can.send_message(0x10242040, '00')
    # data can be spaced by byte, to make it more readable
    can.send_message(0x24c, '11 22 33 44 55 66 77 88')
    # periodic message not in the dbc - cycleTime is in milliseconds
    can.send_message(0x13FFE040, '', inDatabase=False, cycleTime=1000)
    can.send_message(0x64c, '1122334455667788', inDatabase=False, cycleTime=100)

    """send_diag - sends and receives diagnostic messages"""
    logging.info('='*60)
    logging.info('Sending diagnotistic message')
    logging.info('-'*60)
    # Similar to send message for the first two arguments, but the third is the
    # third is the message name you expect a response from. The function
    # returns the data received if there is a response or noting otherwise.

    # The keyword arguements defined for this function are not completely
    # working at this point. This file will be updated with examples when they
    # are.
    can.send_diag('usdt_req_to_ipc_ls', '03B7FE21AAAAAAAA',
                  'usdt_resp_from_ipc_ls')

    """wait_for - waits for a message"""
    logging.info('='*60)
    logging.info('Waiting for System_Power_Mode_LS')
    logging.info('-'*60)
    # Wait for 5.1 seconds for the message system_powermode_ls with any data
    # 5.1 seconds was chosen because the message has a cycle time of 5 seconds.
    can.wait_for(5100, 'system_power_mode_ls', '')
    # also similar to send message, known issue with this, to be fixed shortly
    can.wait_for(1100, 0x13FFE040, '', inDatabase=False)

    """kill_periodic - stop transmitting periodic messages"""
    logging.info('='*60)
    logging.info('Killing single periodics')
    logging.info('-'*60)
    # message by name or by hex value
    can.kill_periodic(0x13FFE040)
    can.kill_periodic('engine_information_1_ls')
    # signal by full name or short name
    can.kill_periodic('vehicle speed average driven')
    can.kill_periodic('syspwrmd')

    """Starting or stopping more than one message at a time"""
    logging.info('='*60)
    logging.info('Starting all periodics except IPC_LS')
    logging.info('-'*60)
    # Start all periodic messages with their initial values from the database
    # except those transmitted by the node 'IPC_LS'
    can.start_periodics('ipc_ls')
    logging.info('='*60)
    logging.info('Killing node BCM_LS')
    logging.info('-'*60)
    # Kill all periodic messages currently being transmitted by node 'BCM_LS'
    can.kill_node('bcm_ls')
    logging.info('='*60)
    logging.info('Calling initbus')
    logging.info('-'*60)
    # Send initialization periodics stored in initbus.py - a more customizable
    # way to initialize the can bus
    initbus.initbus(can)
    logging.info('='*60)
    logging.info('Killing all periodics')
    logging.info('-'*60)
    # Kill all periodics
    can.kill_periodics()
    # Sends a high voltage wake up message to all ECUs on the bus. Some
    # projects require this to be sent before nodes will up from sleep.
    can.hvWakeUp()
    # Stop logging - this is when the log is actually saved to file
    can.stop_logging()

    # Disconnect from the driver
    can.terminate()

if __name__ == "__main__":
    main()
