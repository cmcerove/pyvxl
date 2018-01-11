#!/usr/bin/env python

"""pyvxl's transmit process."""

import logging
from pyvxl.daemon import Daemon
from pyvxl.vxl import VxlCAN

logging.basicConfig(level=logging.INFO)


class Transmit(Daemon):
    """."""

    def __init__(self, channel):
        # TODO: Channel handling with ports
        # Initialize the daemon
        super(Transmit, self).__init__()

    def transmit_msg(self, ):
        if msg[2].updateFunc:
            #msg[3](''.join(['{:02X}'.format(x) for x in msg[0][0].tagData.msg.data]))
            data = unhexlify(msg[2].updateFunc(msg[2]))
            data = create_string_buffer(data, len(data))
            tmpPtr = pointer(data)
            dataPtr = cast(tmpPtr, POINTER(c_ubyte*8))
            msg[0][0].tagData.msg.data = dataPtr.contents
        msgPtr = pointer(c_uint(1))
        tempEvent = event()
        eventPtr = pointer(tempEvent)
        memcpy(eventPtr, msg[0], sizeof(tempEvent))
        transmitMsg(self.portHandle, self.channel, msgPtr, eventPtr)

class transmitThread(Thread):
    """Transmit thread for transmitting all periodic CAN messages"""
    def __init__(self, stpevent, channel, portHandle):
        super(transmitThread, self).__init__()
        self.daemon = True  # thread will die with the program
        self.messages = []
        self.channel = channel
        self.stopped = stpevent
        self.portHandle = portHandle
        self.elapsed = 0
        self.increment = 0
        self.currGcd = 0
        self.currLcm = 0

    def add(self, txID, dlc, data, cycleTime, message):
        """Adds a periodic message to the list of periodics being sent"""
        xlEvent = event()
        memset(pointer(xlEvent), 0, sizeof(xlEvent))
        xlEvent.tag = c_ubyte(0x0A)
        if txID > 0x8000:
            xlEvent.tagData.msg.id = c_ulong(txID | 0x80000000)
        else:
            xlEvent.tagData.msg.id = c_ulong(txID)
        xlEvent.tagData.msg.dlc = c_ushort(dlc)
        xlEvent.tagData.msg.flags = c_ushort(0)
        # Converting from a string to a c_ubyte array
        tmpPtr = pointer(data)
        dataPtr = cast(tmpPtr, POINTER(c_ubyte*8))
        xlEvent.tagData.msg.data = dataPtr.contents
        msgCount = c_uint(1)
        msgPtr = pointer(msgCount)
        eventPtr = pointer(xlEvent)
        for msg in self.messages:
            # If the message is already being sent, replace it with new data
            if msg[0].contents.tagData.msg.id == xlEvent.tagData.msg.id:
                msg[0] = eventPtr
                break
        else:
            self.messages.append([eventPtr, cycleTime, message])
        self.updateTimes()

    def remove(self, txID):
        """Removes a periodic from the list of currently sending periodics"""
        if txID > 0x8000:
            ID = txID | 0x80000000
        else:
            ID = txID
        for msg in self.messages:
            if msg[0].contents.tagData.msg.id == ID:
                self.messages.remove(msg)
                break


if __name__ == '__main__':
    transmit = Transmit()
    transmit.run()
