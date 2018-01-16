#!/usr/bin/env python

"""A common interface to vxlapi functions."""

import os
from ctypes import WinDLL, c_char_p

# Import the vector DLL
if os.name == 'nt':
    try:
        docPath = "c:\\Users\\Public\\Documents\\"
        vxDLL = WinDLL(docPath + "Vector XL Driver Library\\bin\\vxlapi.dll")
    except WindowsError:
        docPath = "c:\\Documents and Settings\\All Users\\Documents\\"
        vxDLL = WinDLL(docPath + "Vector XL Driver Library\\bin\\vxlapi.dll")

# Redefine dll functions
openDriver = vxDLL.xlOpenDriver
closeDriver = vxDLL.xlCloseDriver
openPort = vxDLL.xlOpenPort
closePort = vxDLL.xlClosePort
transmitMsg = vxDLL.xlCanTransmit
receiveMsg = vxDLL.xlReceive
getError = vxDLL.xlGetErrorString
getError.restype = c_char_p
getDriverConfig = vxDLL.xlGetDriverConfig
setBaudrate = vxDLL.xlCanSetChannelBitrate
activateChannel = vxDLL.xlActivateChannel
flushTxQueue = vxDLL.xlCanFlushTransmitQueue
flushRxQueue = vxDLL.xlFlushReceiveQueue
resetClock = vxDLL.xlResetClock
setNotification = vxDLL.xlSetNotification
deactivateChannel = vxDLL.xlDeactivateChannel
setChannelTransceiver = vxDLL.xlCanSetChannelTransceiver
getEventStr = vxDLL.xlGetEventString
getEventStr.restype = c_char_p
