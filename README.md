# pyvxl
A python library for working with the CAN bus through Vector's vxlAPI.

# Features
- Provides the ability to simulate one or more CAN/CAN-FD channels.
    - All done within a single python process using one thread for TX and one
      thread for RX. So the performance of more complicated simulations will
      depend the capability of your PC.
- Importing dbc files and associating them with a channel.
- Logging in a format that's compatible with Vector CANoe/CANalyzer.
- Support for some UDS services (0x22, 0x2E, 0x3101 and 0x3E) with the ability
  to send other services through the same ISO-TP (15765-2) protocol.

# Requirements
- Windows 10
- Python 3.8 or later (32-bit version)
- Vector Drivers for a VN1630, CANcase or similar hardware installed

# Installation Instructions
- Run make.bat

# Example Usage

```
from pyvxl import CAN

# Connects to the vxlAPI.dll and starts TX/RX threads
can = CAN()


# Bit timing settings below are based on the 80MHz clock used by Vector's
# hardware. These set the sample point to 77.5% and the SJW to 20%.
can_baud_arb = 500000
can_tseg1_arb = 123
can_tseg2_arb = 36
can_sjw_arb = 32
can_baud_data = 2000000
can_tseg1_data = 30
can_tseg2_data = 9
can_sjw_data = 8

channel = can.add_channel(num=can_channel,
                          db='Some_dbc_to_import.dbc',
                          baud=can_baud_arb,
                          tseg1_arb=can_tseg1_arb,
                          tseg2_arb=can_tseg2_arb,
                          sjw_arb=can_sjw_arb,
                          data_baud=can_baud_data,
                          tseg1_data=can_tseg1_data,
                          tseg2_data=can_tseg2_data,
                          sjw_data=can_sjw_data)

# Send a message by name using the current message data
channel.send_message('MSG_NAME')
# Send a message by ID using the current message data
channel.send_message(0x123)
# Send a message by name and change the data it sends
channel.send_message('MSG_NAME', '1234')

# If one of the messages above existed in the database and had a period != 0,
# it would be added to the TX thread and sent periodically. channel.stop_message
# would be how you'd remove it from the TX thread.

# Sending a signal with the current value
channel.send_signal('some_signal')
# Sending a symbolic signal and changing the value. This will only work if
# 'SOME_VAL' is included as one of the possible values for this signal.
channel.send_signal('some_signal', 'SOME_VAL')
# Sending a numeric signal and changing the value. Similarly, 1234 needs to be
# in the valid range for this signal.
channel.send_signal('some_signal', 1234)

# Receiving messages
channel.start_queue('expected_rx_msg', queue_size=1000)
# Wait up to 1s to receive 'expected_rx_msg' before timing out. msg_data will
# be returned as None if the timeout occurred.
time_stamp, msg_data = channel.dequeue_msg('expected_rx_msg', timeout=1000)
# Stop the queue when you no longer need it
channel.stop_queue('expected_rx_msg')

# Sending a message and expecting a fast response
msg_data = channel.send_recv('tx_id', '1234' # tx_data, 'rx_id')

# For other available helper functions, see the Channel class in can.py
# See also can_types.py for database related functions or uds.py for UDS functions.
