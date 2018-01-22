#!/usr/bin/env python

"""pyvxl's transmit process."""

import logging
from pywindaemon import Daemon, Task
from pyvxl.vxl import VxlCan

logging.basicConfig(level=logging.INFO)

# TODO: Make sure that all locations where dbc data was assumed to be updated in Vector are now
#       properly updating these values in the daemon as well


class Transmit(Daemon):
    """."""

    def __init__(self, channel=0):
        """."""
        port = 50100 + channel
        # Initialize the daemon
        super(Transmit, self).__init__(port=port, file=__file__)
        self.vxl = VxlCan(channel)
        self.vxl.start()
        self.messages = {}

    def transmit(self, msg_id, msg_data, update_task):
        """Transmit a periodic CAN message."""
        if update_task:
            """
            #msg[3](''.join(['{:02X}'.format(x) for x in msg[0][0].tagData.msg.data]))
            data = unhexlify(msg[2].updateFunc(msg[2]))
            data = create_string_buffer(data, len(data))
            tmpPtr = pointer(data)
            dataPtr = cast(tmpPtr, POINTER(c_ubyte*8))
            msg[0][0].tagData.msg.data = dataPtr.contents
            """
            pass
        self.vxl.send(msg_id, msg_data)

    def add(self, msg_id, msg_data, period, update_task=None):
        """Begin transmitting a message periodically."""
        if not self._is_daemon():
            if msg_id in self.messages:
                self._remove_task(self.messages[msg_id])
            args = (msg_id, msg_data, update_task)
            self.messages[msg_id] = Task(command='transmit', args=args, period=period)
            self._add_task(self.messages[msg_id])
        else:
            logging.error("Transmit.add() called from the Daemon!")

    def remove(self, msg_id):
        """Stop transmitting a message periodically."""
        if not self._is_daemon():
            if msg_id in self.messages:
                self.messages.pop(msg_id)
                self._remove_task(self.messages[msg_id])
            else:
                logging.warning("Message ID {} isn't being transmitted".format(msg_id))
        else:
            logging.error("Transmit.remove() called from the Daemon!")


if __name__ == '__main__':
    transmit = Transmit()
    transmit.run()
